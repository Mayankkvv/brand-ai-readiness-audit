"""
Freshness signal detection for the freshness-corroboration skill.

run_date_signal_checks() accepts an optional pre-rendered rendered_html
(Step 12) so audit-orchestrator can share one render pass across all
rendering-dependent checks instead of this script opening its own separate
Playwright session. Standalone/CLI usage (no pre-fetched html) is
unchanged.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import extruct
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import fetch_rendered_html  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("freshness-corroboration.date_signals")

DATE_META_NAMES = [
    "article:published_time",
    "article:modified_time",
    "og:updated_time",
    "date",
    "last-modified",
    "dcterms.modified",
    "dcterms.created",
]

UPDATED_TEXT_PATTERN = re.compile(
    r"(last\s+updated|updated\s+on|published\s+on|published)\s*[:\-]?\s*"
    r"([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    re.IGNORECASE,
)

COPYRIGHT_PATTERN = re.compile(
    r"(?:©|\(c\)|copyright)\s*(\d{4})(?:\s*[-–]\s*(\d{4}))?", re.IGNORECASE
)


def extract_meta_dates(html: str) -> Dict[str, str]:
    """Pull out known date-related <meta> tags."""
    soup = BeautifulSoup(html, "html.parser")
    found: Dict[str, str] = {}
    for meta in soup.find_all("meta"):
        key = (meta.get("property") or meta.get("name") or "").strip().lower()
        content = (meta.get("content") or "").strip()
        if key in DATE_META_NAMES and content:
            found[key] = content
    return found


def extract_json_ld_dates(html: str, base_url: str) -> Dict[str, List[str]]:
    """Pull datePublished/dateModified out of any JSON-LD blocks."""
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"], uniform=True)
    except Exception as exc:
        logger.warning("JSON-LD extraction failed: %s", exc)
        return {"datePublished": [], "dateModified": []}

    published: List[str] = []
    modified: List[str] = []
    for item in data.get("json-ld", []):
        if item.get("datePublished"):
            published.append(str(item["datePublished"]))
        if item.get("dateModified"):
            modified.append(str(item["dateModified"]))

    return {"datePublished": published, "dateModified": modified}


def extract_visible_updated_text(html: str) -> List[str]:
    """Find plain-text 'last updated' / 'published on' style phrases."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    return [m.group(0).strip() for m in UPDATED_TEXT_PATTERN.finditer(text)][:10]


def extract_copyright_years(html: str) -> List[int]:
    """Find copyright year notices (e.g. '© 2019-2026')."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    years: set[int] = set()
    for match in COPYRIGHT_PATTERN.finditer(text):
        for group in match.groups():
            if group:
                years.add(int(group))
    return sorted(years)


def run_date_signal_checks(url: str, *, rendered_html: Optional[str] = None) -> Observation:
    """
    Collect freshness/date signals for a URL.

    If rendered_html is provided (e.g. by audit-orchestrator's shared
    render pass), it's used directly instead of fetching independently.
    """
    normalized_url = validate_and_normalize_url(url)

    if rendered_html is None:
        try:
            rendered_html = fetch_rendered_html(normalized_url)
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)
            return Observation(
                id="freshness-date-signals",
                skill="freshness-corroboration",
                category="freshness",
                description=(
                    "Detected date/freshness signals: meta tags, JSON-LD dates, "
                    "visible text, copyright years."
                ),
                data={"checked": False, "error": f"render failed: {exc}"},
            )

    meta_dates = extract_meta_dates(rendered_html)
    json_ld_dates = extract_json_ld_dates(rendered_html, normalized_url)
    visible_updated_text = extract_visible_updated_text(rendered_html)
    copyright_years = extract_copyright_years(rendered_html)

    current_year = datetime.now(timezone.utc).year
    latest_copyright_year = max(copyright_years) if copyright_years else None
    copyright_year_gap = (
        current_year - latest_copyright_year if latest_copyright_year is not None else None
    )

    any_date_signal_found = bool(
        meta_dates
        or json_ld_dates["datePublished"]
        or json_ld_dates["dateModified"]
        or visible_updated_text
        or copyright_years
    )

    return Observation(
        id="freshness-date-signals",
        skill="freshness-corroboration",
        category="freshness",
        description=(
            "Detected date/freshness signals: meta tags, JSON-LD dates, "
            "visible text, copyright years."
        ),
        data={
            "checked": True,
            "error": None,
            "meta_dates": meta_dates,
            "json_ld_dates": json_ld_dates,
            "visible_updated_text_matches": visible_updated_text,
            "copyright_years_found": copyright_years,
            "latest_copyright_year": latest_copyright_year,
            "current_year": current_year,
            "copyright_year_gap": copyright_year_gap,
            "any_date_signal_found": any_date_signal_found,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="freshness-corroboration.date_signals",
        description="Detect date/freshness signals on a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_date_signal_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())