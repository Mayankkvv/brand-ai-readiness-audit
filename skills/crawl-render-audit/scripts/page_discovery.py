"""
Representative internal page discovery for the crawl-render-audit skill.

Implements the Adobe brief's crawling strategy (Section 22): identify a
small, bounded set of representative internal pages (about, pricing,
products/services, contact, docs).

Uses the page's FINAL URL after any redirects (not the originally
requested URL) as the basis for same-domain link matching (Step 22 fix -
see prior history for detail on the notion.so -> notion.com case).

Category matching (Step 24 refinement) uses TWO separate keyword sets:
- PATH_KEYWORDS, matched against the candidate URL's path - a strong
  signal, since "/about" or "/pricing" appearing in a URL path is rarely
  accidental.
- TEXT_KEYWORDS, matched against the link's visible text - a weaker
  signal, so ambiguous categories (especially "about") use specific
  multi-word phrases ("about us", "who we are") rather than a bare
  single word. Found necessary via real-world testing on samsung.com,
  where a promotional link reading "All about Galaxy" was incorrectly
  matched as an About-Us page under the original single-word "about"
  keyword - the word "about" is common in ordinary English sentences and
  is a weak signal on its own, unlike in a URL path.

A category matches if EITHER the path or the text keyword set fires.

This is discovery ONLY: it finds and categorizes candidate URLs. Auditing
those pages happens elsewhere (audit-orchestrator/scripts/skill_runner.py).

Generalization note: all keywords are generic fragments/phrases - never
hardcoded to a specific site.

Respects robots.txt: candidate URLs matching a disallowed path pattern
(from the User-agent group that actually applies to us - see
access_checks.py's Step 23 grouping fix) are excluded.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

# Matched against the candidate URL's PATH only. Strong signal - a path
# fragment is rarely coincidental the way an ordinary English word is.
PATH_KEYWORDS: Dict[str, List[str]] = {
    "about": ["about", "who-we-are", "our-story", "company"],
    "products": ["product", "shop", "store", "catalog"],
    "services": ["service", "solutions"],
    "pricing": ["pricing", "plans", "price"],
    "contact": ["contact", "get-in-touch", "support"],
    "documentation": ["docs", "documentation", "developer", "api-reference"],
}

# Matched against the link's visible TEXT only. Weaker signal, so
# ambiguous categories (especially "about") require specific multi-word
# phrases rather than a bare word that could appear in ordinary marketing
# copy (e.g. "All about Galaxy").
TEXT_KEYWORDS: Dict[str, List[str]] = {
    "about": ["about us", "who we are", "our story", "company profile", "about the company"],
    "products": ["products", "our products", "shop now"],
    "services": ["services", "our services"],
    "pricing": ["pricing", "plans", "price list"],
    "contact": ["contact us", "get in touch", "contact sales", "support"],
    "documentation": ["documentation", "developer docs", "api reference", "developers"],
}

CATEGORY_PRIORITY_ORDER = list(PATH_KEYWORDS.keys())
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


def _categorize_link(href_path: str, link_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Categorize a link by checking PATH_KEYWORDS against the URL path
    first (strong signal), then TEXT_KEYWORDS against the link text
    (weaker signal, more specific phrases). Returns (category, matched_via)
    or (None, None) if nothing matches.
    """
    path_lower = href_path.lower()
    for category, keywords in PATH_KEYWORDS.items():
        if any(keyword in path_lower for keyword in keywords):
            return category, "path"

    text_lower = link_text.lower()
    for category, keywords in TEXT_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            return category, "link_text"

    return None, None


def discover_representative_pages(
    base_url: str,
    rendered_html: str,
    disallowed_paths: Optional[List[str]] = None,
    max_additional_pages: int = MAX_ADDITIONAL_PAGES,
) -> List[Dict[str, str]]:
    """
    Find a bounded, categorized set of representative internal pages
    linked from the page at `base_url`. `base_url` MUST be the page's
    actual final URL (after any redirects) for correct domain matching.
    Returns a list of {"url", "category", "link_text", "matched_via"}
    dicts, deduplicated by category (first match wins) and by URL, in the
    brief's suggested priority order.
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
        category, matched_via = _categorize_link(parsed.path, link_text)
        if category is None or category in seen_categories:
            continue

        seen_urls.add(absolute_url)
        seen_categories.add(category)
        candidates.append(
            {
                "url": absolute_url,
                "category": category,
                "link_text": link_text,
                "matched_via": matched_via,
            }
        )

        if len(candidates) >= max_additional_pages:
            break

    candidates.sort(key=lambda c: CATEGORY_PRIORITY_ORDER.index(c["category"]))
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
    redirects to a different registrable domain.
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