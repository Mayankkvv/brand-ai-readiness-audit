"""
Representative internal page discovery for the crawl-render-audit skill.

Implements the Adobe brief's crawling strategy (Section 22): rather than
auditing only the homepage, identify a small, BOUNDED set of representative
internal pages - about, pricing, products/services, contact, docs - so the
audit can catch problems that only show up on those pages (e.g. the
brief's own worked example: a product page's price missing from structured
data, which the homepage alone would never reveal).

This is discovery ONLY (Step 21): it finds and categorizes candidate URLs
from the homepage's own internal links. It does NOT yet run other checks
against those pages - that wiring is a separate, later step, kept
deliberately out of this one so runtime/budget tradeoffs (running 7 checks
against 5+ pages) get their own careful design rather than being rushed in.

Generalization note: categories are matched via generic keyword fragments
(e.g. "about", "pricing", "contact") against link text and URL path -
never hardcoded to any specific site's actual page names, per the brief's
explicit anti-overfitting requirement (Sections 25-26).

Respects robots.txt: candidate URLs matching a disallowed path pattern
(collected by access_checks.py) are excluded. Only same-registrable-domain
links are considered - this never follows off-site links.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import fetch_rendered_html  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("crawl-render-audit.page_discovery")

# Ordered per the brief's own suggested priority (Section 22): about,
# products, services, pricing, contact, documentation. Each category maps
# to generic keyword fragments checked against both the link's URL path
# and its visible text - never a specific site's real page name.
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "about": ["about", "who-we-are", "our-story", "company"],
    "products": ["product", "shop", "store", "catalog"],
    "services": ["service", "solutions"],
    "pricing": ["pricing", "plans", "price"],
    "contact": ["contact", "get-in-touch", "support"],
    "documentation": ["docs", "documentation", "developer", "api-reference"],
}

MAX_ADDITIONAL_PAGES = 5


def _same_registrable_domain(candidate_netloc: str, base_netloc: str) -> bool:
    """Loose same-site check: exact match or a subdomain of the base domain."""
    candidate = candidate_netloc.lower().removeprefix("www.")
    base = base_netloc.lower().removeprefix("www.")
    return candidate == base or candidate.endswith("." + base)


def _is_disallowed(path: str, disallowed_paths: List[str]) -> bool:
    """
    Approximate robots.txt matching using fnmatch, treating '*' as a
    wildcard (many real robots.txt files use extended '*' patterns beyond
    the original spec - e.g. apple.com's robots.txt uses patterns like
    "/*shop/browse/overlay/*"). This is a conservative heuristic, not a
    full RFC-9309 implementation - erring on the side of excluding a
    candidate rather than risking a disallowed crawl.
    """
    for pattern in disallowed_paths:
        if not pattern:
            continue
        if "*" in pattern:
            if fnmatch.fnmatch(path, pattern):
                return True
        elif path.startswith(pattern):
            return True
    return False


def _categorize_link(href_path: str, link_text: str) -> Optional[str]:
    haystack = f"{href_path} {link_text}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return None


def discover_representative_pages(
    homepage_url: str,
    rendered_html: str,
    disallowed_paths: Optional[List[str]] = None,
    max_additional_pages: int = MAX_ADDITIONAL_PAGES,
) -> List[Dict[str, str]]:
    """
    Find a bounded, categorized set of representative internal pages
    linked from the homepage. Returns a list of
    {"url", "category", "link_text"} dicts, in the brief's suggested
    priority order, deduplicated by category (first match wins) and by URL.
    """
    disallowed_paths = disallowed_paths or []
    base_netloc = urlparse(homepage_url).netloc

    soup = BeautifulSoup(rendered_html, "html.parser")
    seen_urls: set[str] = {homepage_url}
    seen_categories: set[str] = set()
    candidates: List[Dict[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute_url = urljoin(homepage_url, href).split("#")[0]
        parsed = urlparse(absolute_url)

        if not _same_registrable_domain(parsed.netloc, base_netloc):
            continue
        if absolute_url in seen_urls:
            continue
        if _is_disallowed(parsed.path, disallowed_paths):
            continue

        link_text = a.get_text(strip=True)
        category = _categorize_link(parsed.path, link_text)
        if category is None or category in seen_categories:
            continue

        seen_urls.add(absolute_url)
        seen_categories.add(category)
        candidates.append({"url": absolute_url, "category": category, "link_text": link_text})

        if len(candidates) >= max_additional_pages:
            break

    # Return in the brief's suggested priority order, not discovery order.
    priority_order = list(CATEGORY_KEYWORDS.keys())
    candidates.sort(key=lambda c: priority_order.index(c["category"]))
    return candidates


def run_page_discovery(
    url: str,
    *,
    rendered_html: Optional[str] = None,
    disallowed_paths: Optional[List[str]] = None,
) -> Observation:
    """
    Discover representative internal pages for a URL and return an
    Observation. If rendered_html is provided (e.g. by audit-orchestrator's
    shared render pass), it's used directly instead of fetching
    independently.
    """
    normalized_url = validate_and_normalize_url(url)

    if rendered_html is None:
        try:
            rendered_html = fetch_rendered_html(normalized_url)
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)
            return Observation(
                id="page-discovery",
                skill="crawl-render-audit",
                category="crawlability",
                description="Discovery of representative internal pages (about, pricing, products, etc.).",
                data={"checked": False, "error": f"render failed: {exc}"},
            )

    candidates = discover_representative_pages(
        normalized_url, rendered_html, disallowed_paths=disallowed_paths
    )

    return Observation(
        id="page-discovery",
        skill="crawl-render-audit",
        category="crawlability",
        description="Discovery of representative internal pages (about, pricing, products, etc.).",
        data={
            "checked": True,
            "error": None,
            "homepage_url": normalized_url,
            "discovered_pages": candidates,
            "note": (
                "Discovery only (Step 21) - these pages are not yet individually "
                "audited by other checks. That wiring is a planned follow-up step."
            ),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crawl-render-audit.page_discovery",
        description="Discover representative internal pages on a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_page_discovery(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())