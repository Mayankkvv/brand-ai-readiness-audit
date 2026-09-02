"""
Shared HTTP/browser fetch helpers used by crawl-render-audit's scripts.

Kept local to this skill's scripts/ folder (rather than in the top-level
common/ package) because these are crawl-render-audit-specific fetch
mechanics that only this skill's checks need directly.
"""

from __future__ import annotations

import httpx
from playwright.sync_api import sync_playwright

USER_AGENT = "BrandAIReadinessAuditor/0.1 (read-only research/hackathon audit bot)"
HTTP_TIMEOUT_SECONDS = 10.0
RENDER_TIMEOUT_MS = 15_000


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
            page.goto(url, wait_until="networkidle", timeout=RENDER_TIMEOUT_MS)
            return page.content()
        finally:
            browser.close()