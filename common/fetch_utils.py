"""
Shared HTTP/browser fetch helpers used across multiple skills.

Originally lived inside crawl-render-audit's scripts/fetchers.py (Step 6),
moved to common/ in Step 8 once freshness-corroboration also needed
identical raw-HTTP and Playwright-rendering logic.

full_render_session() decouples the raw HTTP fetch from the Playwright
render pass (Step 16 fix): a real-world research batch run against
apple.com (and likely other large, media-heavy sites) showed the plain
httpx fetch of a large homepage exceeding the original 10s timeout, which
- because it ran BEFORE the browser opened - crashed the entire shared
render session and took down all 5 rendering-dependent checks, including
the 4 that never needed raw_html at all (image_checks, date_signals,
entity_signals, engagement_checks, intent_alignment). Now a raw-fetch
failure only affects RenderResult.raw_html (set to None, with the error
recorded), and Playwright rendering still proceeds - render_checks.py and
structured_data_checks.py already handle raw_html=None by fetching it
themselves independently.

All rendering functions wait for "load" rather than "networkidle" (Step 9
fix - networkidle is unreliable on sites with continuous background
network activity), plus a short fixed settle delay.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import httpx
from playwright.sync_api import BrowserContext, Page, sync_playwright

logger = logging.getLogger("common.fetch_utils")

USER_AGENT = "BrandAIReadinessAuditor/0.1 (read-only research/hackathon audit bot)"
# Increased from 10.0 (Step 16 fix) - large real-world homepages (e.g.
# apple.com) can take longer than 10s for a plain HTTP client to fully
# read the response body.
HTTP_TIMEOUT_SECONDS = 20.0
RENDER_TIMEOUT_MS = 20_000
POST_LOAD_SETTLE_MS = 1_500
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800

ABOVE_FOLD_TEXT_JS = """
() => {
  const vh = window.innerHeight || document.documentElement.clientHeight;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, null);
  let text = '';
  const seen = new Set();
  let node = walker.nextNode();
  while (node) {
    if (node.children.length === 0) {
      const rect = node.getBoundingClientRect();
      if (rect.top < vh && rect.bottom > 0 && rect.width > 0 && rect.height > 0) {
        const t = (node.innerText || '').trim();
        if (t && !seen.has(t)) {
          seen.add(t);
          text += ' ' + t;
        }
      }
    }
    node = walker.nextNode();
  }
  return text.trim();
}
"""


def fetch_raw_html(url: str) -> str:
    """Fetch the page with a plain HTTP client (no JavaScript execution)."""
    with httpx.Client(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text


def fetch_rendered_html(url: str) -> str:
    """Fetch the page with a real headless browser, after JS execution."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="load", timeout=RENDER_TIMEOUT_MS)
            page.wait_for_timeout(POST_LOAD_SETTLE_MS)
            return page.content()
        finally:
            browser.close()


@contextmanager
def rendered_browser_session(url: str) -> Iterator[Tuple[str, BrowserContext]]:
    """
    Render `url` and yield (rendered_html, browser_context) while the browser
    is still open. Used for standalone/single-check invocation.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            page.goto(url, wait_until="load", timeout=RENDER_TIMEOUT_MS)
            page.wait_for_timeout(POST_LOAD_SETTLE_MS)
            html = page.content()
            yield html, context
        finally:
            browser.close()


@contextmanager
def rendered_page_session(
    url: str,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
) -> Iterator[Page]:
    """
    Render `url` at a fixed viewport size and yield the live Page object
    while the browser is still open. Used for standalone/single-check
    invocation.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": viewport_width, "height": viewport_height},
            )
            page = context.new_page()
            page.goto(url, wait_until="load", timeout=RENDER_TIMEOUT_MS)
            page.wait_for_timeout(POST_LOAD_SETTLE_MS)
            yield page
        finally:
            browser.close()


@dataclass
class RenderResult:
    """
    Bundle of everything a single shared render pass produces.

    raw_html is Optional (Step 16 fix): if the plain HTTP fetch fails, this
    is None and raw_html_error explains why - the Playwright render itself
    still proceeds regardless, since most checks don't need raw_html at all.
    """

    raw_html: Optional[str]
    raw_html_error: Optional[str]
    rendered_html: str
    above_fold_text: str
    context: BrowserContext


@contextmanager
def full_render_session(
    url: str,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
) -> Iterator[RenderResult]:
    """
    Perform ONE Playwright render of `url` and yield a RenderResult bundling
    raw HTML, rendered HTML, above-fold visible text, and the live browser
    context - so multiple specialist checks can share a single render pass.

    The raw HTTP fetch is decoupled from the Playwright render (Step 16
    fix): if it fails or times out, raw_html is None and raw_html_error is
    set, but rendering still proceeds - only render_checks and
    structured_data_checks actually need raw_html, and both already handle
    it being None by fetching it themselves independently.
    """
    raw_html: Optional[str] = None
    raw_html_error: Optional[str] = None
    try:
        raw_html = fetch_raw_html(url)
    except httpx.HTTPError as exc:
        raw_html_error = str(exc)
        logger.warning("Raw HTML fetch failed for %s (rendering will still proceed): %s", url, exc)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": viewport_width, "height": viewport_height},
            )
            page = context.new_page()
            page.goto(url, wait_until="load", timeout=RENDER_TIMEOUT_MS)
            page.wait_for_timeout(POST_LOAD_SETTLE_MS)
            rendered_html = page.content()
            above_fold_text = page.evaluate(ABOVE_FOLD_TEXT_JS)
            yield RenderResult(
                raw_html=raw_html,
                raw_html_error=raw_html_error,
                rendered_html=rendered_html,
                above_fold_text=above_fold_text,
                context=context,
            )
        finally:
            browser.close()