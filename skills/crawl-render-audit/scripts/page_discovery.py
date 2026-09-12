"""
Representative internal page discovery for the crawl-render-audit skill.

Implements the Adobe brief's crawling strategy (Section 22): identify a
small, bounded set of representative internal pages (about, pricing,
products/services, contact, docs) so the audit can catch problems that
only show up on those pages.

Uses the page's FINAL URL after any redirects (not the originally
requested URL) as the basis for same-domain link matching and relative-
link resolution - fixed after real-world testing on notion.so (which
redirects to notion.com, a DIFFERENT registrable domain, not a subdomain)
showed every real link being incorrectly rejected because it was compared
against the pre-redirect domain instead of the domain the page actually
ended up on.

This is discovery ONLY: it finds and categorizes candidate URLs. Auditing
those pages happens elsewhere (audit-orchestrator/scripts/skill_runner.py).

Generalization note: categories are matched via generic keyword fragments
against link text and URL path - never hardcoded to a specific site.

Respects robots.txt: candidate URLs matching a disallowed path pattern are
excluded. Only same-registrable-domain links (relative to the page's ACTUAL
final domain) are considered.
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

from common.fetch_utils import rendered_page_session  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("crawl-render-audit.page_discovery")

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
    """Approximate robots.txt matching, treating '*' as a wildcard."""
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
    base_url: str,
    rendered_html: str,
    disallowed_paths: Optional[List[str]] = None,
    max_additional_pages: int = MAX_ADDITIONAL_PAGES,
) -> List[Dict[str, str]]:
    """
    Find a bounded, categorized set of representative internal pages
    linked from the page at `base_url`. `base_url` MUST be the page's
    actual final URL (after any redirects) for correct domain matching -
    see run_page_discovery(). Returns a list of
    {"url", "category", "link_text"} dicts, deduplicated by category
    (first match wins) and by URL, in the brief's suggested priority order.
    """
    disallowed_paths = disallowed_paths or []
    base_netloc = urlparse(base_url).netloc

    soup = BeautifulSoup(rendered_html, "html.parser")
    seen_urls: set[str] = {base_url}
    seen_categories: set[str] = set()
    candidates: List[Dict[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute_url = urljoin(base_url, href).split("#")[0]
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

    priority_order = list(CATEGORY_KEYWORDS.keys())
    candidates.sort(key=lambda c: priority_order.index(c["category"]))
    return candidates


def run_page_discovery(
    url: str,
    *,
    rendered_html: Optional[str] = None,
    final_url: Optional[str] = None,
    disallowed_paths: Optional[List[str]] = None,
) -> Observation:
    """
    Discover representative internal pages for a URL and return an
    Observation.

    `final_url` (e.g. from audit-orchestrator's shared render pass, via
    RenderResult.final_url) should be the page's ACTUAL URL after any
    redirects - required for correct domain matching if the requested URL
    redirects to a different registrable domain. If rendered_html is
    provided but final_url is not, this falls back to the requested
    (possibly pre-redirect) URL, which may under-discover pages on
    redirecting sites.
    """
    normalized_url = validate_and_normalize_url(url)

    if rendered_html is None:
        try:
            with rendered_page_session(normalized_url) as page:
                rendered_html = page.content()
                final_url = page.url
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)
            return Observation(
                id="page-discovery",
                skill="crawl-render-audit",
                category="crawlability",
                description="Discovery of representative internal pages (about, pricing, products, etc.).",
                data={"checked": False, "error": f"render failed: {exc}"},
            )

    effective_base_url = final_url or normalized_url
    candidates = discover_representative_pages(
        effective_base_url, rendered_html, disallowed_paths=disallowed_paths
    )

    return Observation(
        id="page-discovery",
        skill="crawl-render-audit",
        category="crawlability",
        description="Discovery of representative internal pages (about, pricing, products, etc.).",
        data={
            "checked": True,
            "error": None,
            "requested_url": normalized_url,
            "homepage_url": effective_base_url,
            "discovered_pages": candidates,
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