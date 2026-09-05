"""
Structured data (JSON-LD / microdata / OpenGraph) inspection for the
crawl-render-audit skill.

run_structured_data_checks() accepts optional pre-fetched raw_html/
rendered_html (Step 12) so audit-orchestrator can share one render pass
across all rendering-dependent checks instead of this script opening its
own separate Playwright session. Standalone/CLI usage (no pre-fetched html)
is unchanged.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import extruct
import httpx
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import fetch_raw_html, fetch_rendered_html  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("crawl-render-audit.structured_data_checks")

SYNTAXES = ["json-ld", "microdata", "opengraph"]


def _collect_types(items: List[Dict[str, Any]], type_key: str) -> List[str]:
    """Collect unique @type/type values across a list of structured data items."""
    types: List[str] = []
    for item in items:
        value = item.get(type_key)
        if isinstance(value, list):
            types.extend(str(v) for v in value)
        elif value:
            types.append(str(value))
    return sorted(set(types))


def extract_structured_data(html: str, base_url: str) -> Dict[str, Any]:
    """Run extruct against an HTML document and summarize what was found."""
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=SYNTAXES, uniform=True)
    except Exception as exc:
        logger.warning("Structured data extraction failed: %s", exc)
        return {
            "checked": False,
            "error": str(exc),
            "json_ld_count": 0,
            "json_ld_types": [],
            "microdata_count": 0,
            "microdata_types": [],
            "opengraph_count": 0,
        }

    json_ld_items = data.get("json-ld", [])
    microdata_items = data.get("microdata", [])
    opengraph_items = data.get("opengraph", [])

    return {
        "checked": True,
        "error": None,
        "json_ld_count": len(json_ld_items),
        "json_ld_types": _collect_types(json_ld_items, "@type"),
        "microdata_count": len(microdata_items),
        "microdata_types": _collect_types(microdata_items, "type"),
        "opengraph_count": len(opengraph_items),
    }


def run_structured_data_checks(
    url: str,
    *,
    raw_html: Optional[str] = None,
    rendered_html: Optional[str] = None,
) -> Observation:
    """
    Compare structured data present in raw HTML vs. rendered HTML.

    If raw_html/rendered_html are provided (e.g. by audit-orchestrator's
    shared render pass), they are used directly instead of fetching
    independently.
    """
    normalized_url = validate_and_normalize_url(url)

    if raw_html is None:
        try:
            raw_html = fetch_raw_html(normalized_url)
        except httpx.HTTPError as exc:
            logger.warning("Raw HTML fetch failed for %s: %s", normalized_url, exc)
            return Observation(
                id="structured-data",
                skill="crawl-render-audit",
                category="structured_data",
                description="Structured data (JSON-LD/microdata/OpenGraph) presence and type.",
                data={"checked": False, "error": f"raw fetch failed: {exc}"},
            )

    raw_result = extract_structured_data(raw_html, normalized_url)

    rendered_result = None
    if rendered_html is not None:
        rendered_result = extract_structured_data(rendered_html, normalized_url)
    else:
        try:
            fetched_rendered_html = fetch_rendered_html(normalized_url)
            rendered_result = extract_structured_data(fetched_rendered_html, normalized_url)
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)

    only_after_rendering = None
    if rendered_result is not None:
        only_after_rendering = (
            raw_result["json_ld_count"] == 0 and rendered_result["json_ld_count"] > 0
        )

    return Observation(
        id="structured-data",
        skill="crawl-render-audit",
        category="structured_data",
        description="Structured data (JSON-LD/microdata/OpenGraph) presence and type.",
        data={
            "raw": raw_result,
            "rendered": rendered_result,
            "json_ld_only_appears_after_rendering": only_after_rendering,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crawl-render-audit.structured_data_checks",
        description="Inspect structured data (JSON-LD/microdata/OpenGraph) on a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_structured_data_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())