"""
First-screen orientation and trust/navigation checks for the
engagement-audit skill.

Covers four of the skill's five planned areas, all as deterministic,
pattern-based measurements (Observations, not judgments):
  - First-screen orientation: title, meta description, first heading, and
    the actual visible text above the fold (via a live rendered viewport).
  - Navigation / next-step clarity: presence and count of call-to-action
    links/buttons using generic action-verb patterns.
  - Trust / credibility signals: contact/about links, social profile
    links, and visible phone/email patterns.
  - Content clarity: a Flesch reading-ease score over the page's visible
    text, as a generic, library-based proxy for how easy the text is to
    read (not a judgment that a low score is automatically a problem).

The remaining two planned areas - intent-to-landing alignment and context
retention - require knowing what an AI assistant told the visitor before
they arrived. No such "assumed intent" input exists yet, so those are
deferred until the orchestrator can supply that context (see SKILL.md).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import textstat
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import rendered_page_session  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("engagement-audit.engagement_checks")

# Generic, non-brand-specific action verbs commonly used in calls to action.
# Intentionally broad/pattern-based so this generalizes to unseen websites,
# not tuned to any specific site's wording.
CTA_KEYWORDS = [
    "buy", "shop", "get started", "sign up", "signup", "subscribe", "download",
    "book now", "book a", "learn more", "contact us", "contact sales",
    "request a demo", "try free", "try it free", "start free", "start your",
    "register", "apply now", "join now", "add to cart", "order now", "schedule",
]

PHONE_PATTERN = re.compile(r"(\+?\d[\d\-.\s()]{7,}\d)")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SOCIAL_DOMAINS = [
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "tiktok.com",
]

MAX_CTA_SAMPLES = 8
MAX_ABOVE_FOLD_CHARS_FOR_SAMPLE = 400

# JS run inside the rendered page to find leaf elements whose bounding box
# overlaps the initial viewport (i.e. visible without scrolling).
_ABOVE_FOLD_TEXT_JS = """
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
    # Deduplicate while preserving order, then cap the sample size.
    seen: set[str] = set()
    unique_matches: List[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique_matches.append(m)
    return unique_matches[:MAX_CTA_SAMPLES]


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

    phone_matches = PHONE_PATTERN.findall(page_text)
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


def run_engagement_checks(url: str) -> List[Observation]:
    """Run all Step 9 engagement checks for a URL and return Observations."""
    normalized_url = validate_and_normalize_url(url)

    try:
        with rendered_page_session(normalized_url) as page:
            html = page.content()
            above_fold_text = page.evaluate(_ABOVE_FOLD_TEXT_JS)
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

    soup = BeautifulSoup(html, "html.parser")
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