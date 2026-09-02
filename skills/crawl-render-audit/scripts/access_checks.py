"""
Deterministic crawlability checks for the crawl-render-audit skill.

Current checks (Step 4):
- HTTP accessibility of the homepage (status code, redirect chain)
- robots.txt presence, disallowed paths, and declared sitemaps
- Sitemap discovery and basic parsing (URL count + sample URLs)

These produce Observations only - raw measured facts. Deciding whether an
observation represents an actual problem (a Finding) happens later, in the
orchestrator's reasoning layer, not here.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("crawl-render-audit")

USER_AGENT = "BrandAIReadinessAuditor/0.1 (read-only research/hackathon audit bot)"
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_SITEMAP_SAMPLE_URLS = 5


def check_http_status(client: httpx.Client, url: str) -> Dict[str, Any]:
    """Fetch the URL and report status code + redirect chain."""
    try:
        response = client.get(url, follow_redirects=True)
        redirect_chain = [str(r.url) for r in response.history] + [str(response.url)]
        return {
            "checked": True,
            "requested_url": url,
            "final_url": str(response.url),
            "status_code": response.status_code,
            "redirect_count": len(response.history),
            "redirect_chain": redirect_chain,
            "error": None,
        }
    except httpx.HTTPError as exc:
        logger.warning("HTTP check failed for %s: %s", url, exc)
        return {
            "checked": False,
            "requested_url": url,
            "final_url": None,
            "status_code": None,
            "redirect_count": None,
            "redirect_chain": None,
            "error": str(exc),
        }


def fetch_robots_txt(client: httpx.Client, base_url: str) -> Dict[str, Any]:
    """Fetch and parse robots.txt for disallowed paths and declared sitemaps."""
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        response = client.get(robots_url, follow_redirects=True)
    except httpx.HTTPError as exc:
        logger.warning("robots.txt fetch failed for %s: %s", robots_url, exc)
        return {
            "checked": False,
            "robots_url": robots_url,
            "exists": None,
            "status_code": None,
            "disallowed_paths": [],
            "sitemap_urls": [],
            "error": str(exc),
        }

    if response.status_code != 200:
        return {
            "checked": True,
            "robots_url": robots_url,
            "exists": False,
            "status_code": response.status_code,
            "disallowed_paths": [],
            "sitemap_urls": [],
            "error": None,
        }

    disallowed_paths: List[str] = []
    sitemap_urls: List[str] = []
    for raw_line in response.text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lowered = line.lower()
        if lowered.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                disallowed_paths.append(path)
        elif lowered.startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            if sitemap_url:
                sitemap_urls.append(sitemap_url)

    return {
        "checked": True,
        "robots_url": robots_url,
        "exists": True,
        "status_code": 200,
        "disallowed_paths": disallowed_paths,
        "sitemap_urls": sitemap_urls,
        "error": None,
    }


def _parse_sitemap_urls(xml_bytes: bytes) -> tuple[int, List[str]]:
    """Parse a sitemap XML document, returning (total_url_count, sample_urls)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return 0, []

    urls: List[str] = []
    for elem in root.iter():
        # Strip XML namespace prefix, e.g. "{http://.../sitemap}loc" -> "loc"
        tag = elem.tag.split("}")[-1]
        if tag == "loc" and elem.text:
            urls.append(elem.text.strip())

    return len(urls), urls[:MAX_SITEMAP_SAMPLE_URLS]


def discover_sitemap(
    client: httpx.Client, base_url: str, robots_sitemap_urls: List[str]
) -> Dict[str, Any]:
    """Try robots.txt-declared sitemaps first, then fall back to /sitemap.xml."""
    candidates = list(robots_sitemap_urls)
    fallback_url = urljoin(base_url, "/sitemap.xml")
    if fallback_url not in candidates:
        candidates.append(fallback_url)

    for candidate in candidates:
        try:
            response = client.get(candidate, follow_redirects=True)
        except httpx.HTTPError as exc:
            logger.warning("Sitemap fetch failed for %s: %s", candidate, exc)
            continue

        if response.status_code == 200 and response.content:
            url_count, sample_urls = _parse_sitemap_urls(response.content)
            return {
                "checked": True,
                "found": True,
                "sitemap_url": candidate,
                "url_count": url_count,
                "sample_urls": sample_urls,
                "source": "robots.txt" if candidate in robots_sitemap_urls else "default_path",
                "error": None,
            }

    return {
        "checked": True,
        "found": False,
        "sitemap_url": None,
        "url_count": 0,
        "sample_urls": [],
        "source": None,
        "error": None,
    }


def run_access_checks(url: str) -> List[Observation]:
    """Run all Step 4 crawlability checks for a URL and return Observations."""
    normalized_url = validate_and_normalize_url(url)
    observations: List[Observation] = []

    with httpx.Client(
        timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        http_result = check_http_status(client, normalized_url)
        observations.append(
            Observation(
                id="crawl-http-status",
                skill="crawl-render-audit",
                category="crawlability",
                description="HTTP accessibility and redirect behavior of the homepage.",
                data=http_result,
            )
        )

        robots_result = fetch_robots_txt(client, normalized_url)
        observations.append(
            Observation(
                id="crawl-robots-txt",
                skill="crawl-render-audit",
                category="crawlability",
                description="robots.txt presence, disallowed paths, and declared sitemaps.",
                data=robots_result,
            )
        )

        robots_sitemaps = robots_result["sitemap_urls"] if robots_result["exists"] else []
        sitemap_result = discover_sitemap(client, normalized_url, robots_sitemaps)
        observations.append(
            Observation(
                id="crawl-sitemap",
                skill="crawl-render-audit",
                category="crawlability",
                description="Sitemap discovery and basic structure.",
                data=sitemap_result,
            )
        )

    return observations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crawl-render-audit.access_checks",
        description="Run HTTP/robots.txt/sitemap checks against a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observations = run_access_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps([o.model_dump() for o in observations], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())