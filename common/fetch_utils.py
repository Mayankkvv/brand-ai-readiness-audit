"""
Shared HTTP/browser fetch helpers used across multiple skills.

Originally lived inside crawl-render-audit's scripts/fetchers.py (Step 6),
moved to common/ in Step 8 once freshness-corroboration also needed
identical raw-HTTP and Playwright-rendering logic.

rendered_browser_session() was added to fix a real issue found during
testing: some CDNs (e.g. Wikimedia) return 403 Forbidden to a bare HTTP
client requesting a static asset directly, but serve the identical asset
fine to a real browser session. Keeping the browser context open lets
callers fetch additional resources (like images) the same way the browser
would.

rendered_page_session() was added in Step 9 for engagement-audit, which
needs to run JavaScript in the page (via page.evaluate) to determine what
content is actually visible above the fold - something that can't be
determined from static HTML alone.

All three rendering functions wait for "load" rather than "networkidle".
"networkidle" (no network activity for 500ms) is unreliable on real sites
with continuous background activity - analytics beacons, ads, chat widgets,
periodic pings - which can prevent it from ever firing even though the page
is fully loaded and usable (found via testing against python.org, Step 9).
"load" plus a short fixed settle delay is a more robust default for
general-purpose auditing of unseen websites.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Tuple

import httpx
from playwright.sync_api import BrowserContext, Page, sync_playwright

USER_AGENT = "BrandAIReadinessAuditor/0.1 (read-only research/hackathon audit bot)"
HTTP_TIMEOUT_SECONDS = 10.0
RENDER_TIMEOUT_MS = 20_000
# Short fixed wait after "load" fires, giving quick post-load JS a chance to
# run without depending on the unreliable "networkidle" signal.
POST_LOAD_SETTLE_MS = 1_500
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800


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
    Some CDNs block a bare HTTP client fetching a static asset directly but
    serve the same asset fine via/alongside a real browser session.
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
    inspect actual rendered layout (e.g. what's visible above the fold) -
    something that can't be determined from a static HTML string alone.
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