"""
First-screen orientation and trust/navigation checks for the
engagement-audit skill.

run_engagement_checks() accepts optional pre-rendered rendered_html/
above_fold_text (Step 12) so audit-orchestrator can share one render pass
across all rendering-dependent checks instead of this script opening its
own separate Playwright session. Standalone/CLI usage (no pre-fetched
render) is unchanged.

Phone number detection uses the `phonenumbers` library (Google's
libphonenumber) rather than a hand-rolled regex, after real-world testing
against python.org produced false positives (a float, a date stamp, a
Fibonacci-sequence code example) from a loose digit-pattern regex.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import phonenumbers
import textstat
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import ABOVE_FOLD_TEXT_JS, rendered_page_session  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("engagement-audit.engagement_checks")

CTA_KEYWORDS = [
    "buy", "shop", "get started", "sign up", "signup", "subscribe", "download",
    "book now", "book a", "learn more", "contact us", "contact sales",
    "request a demo", "try free", "try it free", "start free", "start your",
    "register", "apply now", "join now", "add to cart", "order now", "schedule",
]

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SOCIAL_DOMAINS = [
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "tiktok.com",
]

PHONE_MATCHER_DEFAULT_REGION = "US"
MAX_PHONE_SCAN_CHARS = 20_000

MAX_CTA_SAMPLES = 8
MAX_ABOVE_FOLD_CHARS_FOR_SAMPLE = 400


def _extract_page_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Pull title, meta description, and the first H1 heading."""
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()

    h1_tag = soup.find("h1")
    first_h1 = h1_tag.get_text(strip=True) if h1_tag else None

    return {
        "title": title,
        "meta_description": description,
        "first_h1": first_h1,
    }


def _find_cta_elements(soup: BeautifulSoup) -> List[str]:
    """Find <a>/<button> elements whose text matches common CTA phrasing."""
    matches: List[str] = []
    for el in soup.find_all(["a", "button"]):
        text = el.get_text(strip=True)
        if not text:
            continue
        lowered = text.lower()
        if any(keyword in lowered for keyword in CTA_KEYWORDS):
            matches.append(text)
    seen: set[str] = set()
    unique_matches: List[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique_matches.append(m)
    return unique_matches[:MAX_CTA_SAMPLES]


def _find_phone_numbers(page_text: str) -> List[str]:
    """Find valid phone numbers using phonenumbers (libphonenumber)."""
    scan_text = page_text[:MAX_PHONE_SCAN_CHARS]
    matches: List[str] = []
    try:
        for match in phonenumbers.PhoneNumberMatcher(scan_text, PHONE_MATCHER_DEFAULT_REGION):
            matches.append(match.raw_string)
    except Exception as exc:
        logger.warning("Phone number scan failed: %s", exc)
    return matches


def _find_trust_navigation_signals(soup: BeautifulSoup, page_text: str) -> Dict[str, Any]:
    """Detect contact/about links, social profile links, phone/email patterns."""
    links = soup.find_all("a", href=True)

    contact_link_present = any(
        "contact" in (a.get_text(strip=True).lower() + " " + a["href"].lower())
        for a in links
    )
    about_link_present = any(
        "about" in (a.get_text(strip=True).lower() + " " + a["href"].lower())
        for a in links
    )

    social_domains_found: set[str] = set()
    for a in links:
        href = a["href"].lower()
        for domain in SOCIAL_DOMAINS:
            if domain in href:
                social_domains_found.add(domain)

    phone_matches = _find_phone_numbers(page_text)
    email_matches = EMAIL_PATTERN.findall(page_text)

    return {
        "contact_link_present": contact_link_present,
        "about_link_present": about_link_present,
        "social_domains_found": sorted(social_domains_found),
        "phone_pattern_found": len(phone_matches) > 0,
        "phone_pattern_sample": phone_matches[0].strip() if phone_matches else None,
        "email_pattern_found": len(email_matches) > 0,
        "email_pattern_sample": email_matches[0] if email_matches else None,
    }


def _compute_readability(page_text: str) -> Dict[str, Any]:
    """Flesch reading-ease score - a generic proxy for content clarity."""
    word_count = len(page_text.split())
    if word_count < 30:
        return {
            "checked": False,
            "reason": "insufficient visible text to compute a reliable score",
            "flesch_reading_ease": None,
            "word_count": word_count,
        }
    score = textstat.flesch_reading_ease(page_text)
    return {
        "checked": True,
        "reason": None,
        "flesch_reading_ease": round(score, 1),
        "word_count": word_count,
    }


def run_engagement_checks(
    url: str,
    *,
    rendered_html: Optional[str] = None,
    above_fold_text: Optional[str] = None,
) -> List[Observation]:
    """
    Run all engagement checks for a URL and return Observations.

    If rendered_html/above_fold_text are provided (e.g. by
    audit-orchestrator's shared render pass), they are used directly
    instead of opening a separate Playwright session.
    """
    normalized_url = validate_and_normalize_url(url)

    if rendered_html is None or above_fold_text is None:
        try:
            with rendered_page_session(normalized_url) as page:
                rendered_html = page.content()
                above_fold_text = page.evaluate(ABOVE_FOLD_TEXT_JS)
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)
            error_data = {"checked": False, "error": f"render failed: {exc}"}
            return [
                Observation(
                    id="engagement-first-screen",
                    skill="engagement-audit",
                    category="engagement",
                    description="First-screen orientation: title, meta description, H1, above-fold text.",
                    data=error_data,
                ),
                Observation(
                    id="engagement-trust-navigation",
                    skill="engagement-audit",
                    category="engagement",
                    description="Call-to-action, trust, and navigation signal detection.",
                    data=error_data,
                ),
            ]

    soup = BeautifulSoup(rendered_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    full_page_text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    metadata = _extract_page_metadata(soup)
    above_fold_word_count = len(above_fold_text.split())
    readability = _compute_readability(full_page_text)

    first_screen_observation = Observation(
        id="engagement-first-screen",
        skill="engagement-audit",
        category="engagement",
        description="First-screen orientation: title, meta description, H1, above-fold text.",
        data={
            "checked": True,
            "error": None,
            **metadata,
            "above_fold_word_count": above_fold_word_count,
            "above_fold_text_sample": above_fold_text[:MAX_ABOVE_FOLD_CHARS_FOR_SAMPLE],
            "readability": readability,
        },
    )

    cta_matches = _find_cta_elements(soup)
    trust_nav_signals = _find_trust_navigation_signals(soup, full_page_text)

    trust_navigation_observation = Observation(
        id="engagement-trust-navigation",
        skill="engagement-audit",
        category="engagement",
        description="Call-to-action, trust, and navigation signal detection.",
        data={
            "checked": True,
            "error": None,
            "cta_matches_found": len(cta_matches),
            "cta_text_samples": cta_matches,
            **trust_nav_signals,
        },
    )

    return [first_screen_observation, trust_navigation_observation]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="engagement-audit.engagement_checks",
        description="Run first-screen orientation and trust/navigation checks on a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observations = run_engagement_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps([o.model_dump() for o in observations], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())