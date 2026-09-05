"""
Shared HTTP/browser fetch helpers used across multiple skills.

Originally lived inside crawl-render-audit's scripts/fetchers.py (Step 6),
moved to common/ in Step 8 once freshness-corroboration also needed
identical raw-HTTP and Playwright-rendering logic.

rendered_browser_session() and rendered_page_session() support a SINGLE
check opening its own render (used for standalone/CLI invocation of an
individual script). full_render_session() (Step 12) supports MULTIPLE
checks sharing ONE render pass - added after real-world testing showed
5 separate per-audit Playwright sessions against the same page caused
intermittent timeouts and unnecessary runtime overhead. audit-orchestrator
uses full_render_session(); each script's own standalone CLI still uses
rendered_browser_session()/rendered_page_session()/fetch_rendered_html()
independently, unchanged.

All rendering functions wait for "load" rather than "networkidle" (see
Step 9 fix - networkidle is unreliable on sites with continuous background
network activity), plus a short fixed settle delay.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Tuple

import httpx
from playwright.sync_api import BrowserContext, Page, sync_playwright

USER_AGENT = "BrandAIReadinessAuditor/0.1 (read-only research/hackathon audit bot)"
HTTP_TIMEOUT_SECONDS = 10.0
RENDER_TIMEOUT_MS = 20_000
POST_LOAD_SETTLE_MS = 1_500
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800

# Shared JS used to determine what's actually visible "above the fold" -
# needs real rendered layout (getBoundingClientRect), which only exists
# while the page is live in the browser. Used by both engagement_checks.py
# (standalone) and full_render_session() (shared pass).
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
    is still open, so callers can fetch additional resources (e.g. images)
    through context.request - inheriting realistic browser request behavior.
    Used for standalone/single-check invocation; see full_render_session()
    for the shared-across-multiple-checks version used by the orchestrator.
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
    while the browser is still open, so callers can run page.evaluate() to
    inspect actual rendered layout (e.g. what's visible above the fold).
    Used for standalone/single-check invocation; see full_render_session()
    for the shared-across-multiple-checks version used by the orchestrator.
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
    """Bundle of everything a single shared render pass produces."""

    raw_html: str
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
    raw HTML (fetched separately and cheaply via httpx), rendered HTML,
    above-fold visible text, and the live browser context - so multiple
    specialist checks (render diff, structured data, image OCR, date
    signals, engagement checks) can share a single render pass instead of
    each independently launching its own browser and re-navigating to the
    same URL (Step 12 - added after real-world testing showed 5 separate
    per-audit Playwright sessions caused intermittent timeouts).

    The browser stays open for the duration of the `with` block, so callers
    that need to download additional resources (e.g. images, via
    context.request) can do so before the browser closes.
    """
    raw_html = fetch_raw_html(url)

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
                rendered_html=rendered_html,
                above_fold_text=above_fold_text,
                context=context,
            )
        finally:
            browser.close()