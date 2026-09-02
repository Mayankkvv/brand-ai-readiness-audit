"""
Hidden / non-text fact detection for the crawl-render-audit skill.

Detects cases where important text-based claims exist only inside images
(e.g. a banner graphic saying "Available in 50 cities") with no equivalent
readable text elsewhere on the page. Uses OCR (Tesseract via pytesseract) -
a deterministic, reproducible extraction step, NOT an LLM. Whether an
image's extracted text represents an actually important, missing claim is
judged later; this script only measures which images contain substantial
text that doesn't already appear in the page's readable content.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
import pytesseract
from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import Error as PlaywrightError

from fetchers import HTTP_TIMEOUT_SECONDS, USER_AGENT, fetch_rendered_html  # sibling module
from render_checks import extract_visible_text  # sibling module

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("crawl-render-audit.image_checks")

# Optional: point pytesseract at a specific Tesseract binary via env var,
# useful on Windows if it isn't on PATH.
_tesseract_cmd = os.environ.get("TESSERACT_CMD")
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

MAX_IMAGES_TO_SCAN = 8
MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 120
MIN_OCR_WORDS_TO_CONSIDER = 4
SKIP_FILENAME_HINTS = ("icon", "logo", "sprite", "favicon", "avatar")


def _looks_like_decorative_filename(src: str) -> bool:
    lowered = src.lower()
    return any(hint in lowered for hint in SKIP_FILENAME_HINTS)


def _extract_candidate_image_urls(rendered_html: str, base_url: str) -> List[Dict[str, Any]]:
    """Find <img> tags likely to carry real content (not icons/tracking pixels)."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    candidates: List[Dict[str, Any]] = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src or src.startswith("data:"):
            continue
        if _looks_like_decorative_filename(src):
            continue

        absolute_url = urljoin(base_url, src)

        declared_width_raw = img.get("width")
        declared_height_raw = img.get("height")
        try:
            declared_width = int(declared_width_raw) if declared_width_raw else None
            declared_height = int(declared_height_raw) if declared_height_raw else None
        except ValueError:
            declared_width = declared_height = None

        candidates.append(
            {
                "url": absolute_url,
                "alt_text": (img.get("alt") or "").strip(),
                "declared_width": declared_width,
                "declared_height": declared_height,
            }
        )

    return candidates


def _download_image(client: httpx.Client, image_url: str) -> Optional[Image.Image]:
    try:
        response = client.get(image_url, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as exc:  # network errors, decode errors, unsupported formats
        logger.warning("Could not download/decode image %s: %s", image_url, exc)
        return None


def _word_overlap_ratio(ocr_text: str, page_text: str) -> float:
    """Fraction of distinct OCR words that also appear in the page's visible text."""
    ocr_words = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", ocr_text)}
    if not ocr_words:
        return 1.0  # no meaningful words to be "missing"
    page_words = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", page_text)}
    matched = ocr_words & page_words
    return round(len(matched) / len(ocr_words), 3)


def run_image_text_checks(url: str) -> Observation:
    """Scan a bounded set of content images for text not present elsewhere on the page."""
    normalized_url = validate_and_normalize_url(url)

    try:
        rendered_html = fetch_rendered_html(normalized_url)
    except PlaywrightError as exc:
        logger.warning("Rendering failed for %s: %s", normalized_url, exc)
        return Observation(
            id="image-hidden-text",
            skill="crawl-render-audit",
            category="non_text_content",
            description="Detection of text-based claims that exist only inside images.",
            data={"checked": False, "error": f"render failed: {exc}"},
        )

    page_text = extract_visible_text(rendered_html)
    candidates = _extract_candidate_image_urls(rendered_html, normalized_url)

    # Prioritize larger declared images first; images with no declared size go last.
    candidates.sort(
        key=lambda c: (c["declared_width"] or 0) * (c["declared_height"] or 0),
        reverse=True,
    )
    candidates = candidates[:MAX_IMAGES_TO_SCAN]

    results: List[Dict[str, Any]] = []
    tesseract_available = True

    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        for candidate in candidates:
            image = _download_image(client, candidate["url"])
            if image is None:
                continue

            width, height = image.size
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                continue

            try:
                ocr_text = pytesseract.image_to_string(image).strip()
            except pytesseract.TesseractNotFoundError:
                tesseract_available = False
                break
            except Exception as exc:
                logger.warning("OCR failed on %s: %s", candidate["url"], exc)
                continue

            word_count = len(re.findall(r"[a-zA-Z]{3,}", ocr_text))
            if word_count < MIN_OCR_WORDS_TO_CONSIDER:
                continue

            overlap_ratio = _word_overlap_ratio(ocr_text, page_text)
            results.append(
                {
                    "image_url": candidate["url"],
                    "alt_text": candidate["alt_text"],
                    "image_width": width,
                    "image_height": height,
                    "ocr_word_count": word_count,
                    "ocr_text_sample": ocr_text[:200],
                    "word_overlap_ratio_with_page_text": overlap_ratio,
                    "likely_text_only_in_image": overlap_ratio < 0.5,
                }
            )

    if not tesseract_available:
        return Observation(
            id="image-hidden-text",
            skill="crawl-render-audit",
            category="non_text_content",
            description="Detection of text-based claims that exist only inside images.",
            data={
                "checked": False,
                "error": (
                    "Tesseract OCR engine not found. Install it and ensure it's on "
                    "PATH, or set the TESSERACT_CMD environment variable."
                ),
            },
        )

    images_with_likely_hidden_text = sum(
        1 for r in results if r["likely_text_only_in_image"]
    )

    return Observation(
        id="image-hidden-text",
        skill="crawl-render-audit",
        category="non_text_content",
        description="Detection of text-based claims that exist only inside images.",
        data={
            "checked": True,
            "error": None,
            "candidate_images_found": len(candidates),
            "images_scanned": len(results),
            "images_with_likely_hidden_text": images_with_likely_hidden_text,
            "images": results,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crawl-render-audit.image_checks",
        description="Detect text-based claims that exist only inside images on a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_image_text_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())