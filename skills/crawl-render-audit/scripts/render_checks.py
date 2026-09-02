"""
Raw-HTML-vs-rendered-DOM comparison for the crawl-render-audit skill.

Measures how much visible text content only becomes available after
JavaScript execution. This is a pure measurement (Observation) - deciding
whether the measured gap represents a real extractability problem happens
later, in the orchestrator's reasoning layer, not here.

Per the project's design principle: using JavaScript is not itself a
problem. Only a meaningful, evidence-backed content gap is worth flagging,
and that judgment is intentionally deferred.
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import fetch_raw_html, fetch_rendered_html  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("crawl-render-audit.render_checks")

MAX_COMPARE_CHARS = 20_000


def extract_visible_text(html: str) -> str:
    """Strip tags/scripts/styles and return normalized visible text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def compute_render_diff(raw_html: str, rendered_html: str) -> Dict[str, Any]:
    """Compute measured differences between raw and rendered content."""
    raw_text = extract_visible_text(raw_html)
    rendered_text = extract_visible_text(rendered_html)

    raw_word_count = len(raw_text.split())
    rendered_word_count = len(rendered_text.split())
    word_count_delta = rendered_word_count - raw_word_count
    word_count_increase_pct = (
        round((word_count_delta / raw_word_count) * 100, 1) if raw_word_count > 0 else None
    )

    matcher = difflib.SequenceMatcher(
        None, raw_text[:MAX_COMPARE_CHARS], rendered_text[:MAX_COMPARE_CHARS]
    )
    similarity_ratio = round(matcher.ratio(), 3)

    return {
        "checked": True,
        "raw_html_char_count": len(raw_html),
        "rendered_html_char_count": len(rendered_html),
        "raw_visible_text_word_count": raw_word_count,
        "rendered_visible_text_word_count": rendered_word_count,
        "word_count_delta": word_count_delta,
        "word_count_increase_percent": word_count_increase_pct,
        "text_similarity_ratio": similarity_ratio,
        "error": None,
    }


def run_render_checks(url: str) -> Observation:
    """Run the raw-vs-rendered comparison for a URL and return an Observation."""
    normalized_url = validate_and_normalize_url(url)

    try:
        raw_html = fetch_raw_html(normalized_url)
    except httpx.HTTPError as exc:
        logger.warning("Raw HTML fetch failed for %s: %s", normalized_url, exc)
        return Observation(
            id="render-diff",
            skill="crawl-render-audit",
            category="rendering",
            description="Comparison of raw HTML vs. rendered DOM visible text.",
            data={"checked": False, "error": f"raw fetch failed: {exc}"},
        )

    try:
        rendered_html = fetch_rendered_html(normalized_url)
    except PlaywrightError as exc:
        logger.warning("Rendering failed for %s: %s", normalized_url, exc)
        return Observation(
            id="render-diff",
            skill="crawl-render-audit",
            category="rendering",
            description="Comparison of raw HTML vs. rendered DOM visible text.",
            data={"checked": False, "error": f"render failed: {exc}"},
        )

    diff_data = compute_render_diff(raw_html, rendered_html)
    return Observation(
        id="render-diff",
        skill="crawl-render-audit",
        category="rendering",
        description="Comparison of raw HTML vs. rendered DOM visible text.",
        data=diff_data,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crawl-render-audit.render_checks",
        description="Compare raw HTML vs. rendered DOM for a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_render_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())