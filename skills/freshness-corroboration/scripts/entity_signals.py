"""
Entity identity signal detection for the freshness-corroboration skill.

Covers the "claim consistency" and "entity ambiguity" areas from the
brief: can a machine confidently determine which entity this website
represents, and do the site's various self-descriptions agree with each
other? This is a pure evidence-collection step (an Observation) - it does
NOT judge whether the site's identity is actually ambiguous or
inconsistent. That judgment is deferred to audit-orchestrator's Gemini
reasoning stage, which receives this observation alongside every other
skill's evidence in one combined call - avoiding a second, separate
LLM call per audit (per the project's "keep Gemini usage efficient" rule).

Scope note: this does NOT check claims against independent external
sources (e.g. live web search for corroboration/contradiction). That would
require additional LLM/search calls per audit, working against the
5-minute runtime and free-tier rate-limit constraints. This is a
deliberate, documented scope boundary, not an oversight - see
context/DECISIONS.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import extruct
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import fetch_rendered_html  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("freshness-corroboration.entity_signals")

ENTITY_JSON_LD_TYPES = {
    "organization", "localbusiness", "corporation", "website",
    "webpage", "person", "brand",
}

# Deliberately conservative: requires a leading number, a short word run,
# and a recognizable street-type suffix. Reduces false positives compared
# to a loose digit-and-word pattern (lesson learned from the phone-number
# false-positive rounds in engagement_checks.py).
ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.\s]{2,40}?"
    r"(?:Street|St\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Road|Rd\.?|Lane|Ln\.?|"
    r"Drive|Dr\.?|Suite|Ste\.?|Floor|Fl\.?)\b",
    re.IGNORECASE,
)

COPYRIGHT_NAME_PATTERN = re.compile(
    r"(?:©|\(c\)|copyright)\s*\d{4}(?:\s*[-–]\s*\d{4})?\s*,?\s*([A-Z][A-Za-z0-9&.,'\s]{2,60})",
)

MAX_SAMEAS_LINKS = 10
MAX_ADDRESS_SAMPLES = 3


def _extract_json_ld_entities(html: str, base_url: str) -> List[Dict[str, Any]]:
    """Pull name/url/logo/sameAs from JSON-LD items describing an entity."""
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"], uniform=True)
    except Exception as exc:
        logger.warning("JSON-LD extraction failed: %s", exc)
        return []

    entities: List[Dict[str, Any]] = []
    for item in data.get("json-ld", []):
        raw_type = item.get("@type")
        types = raw_type if isinstance(raw_type, list) else [raw_type] if raw_type else []
        types_lower = {str(t).lower() for t in types}
        if not types_lower & ENTITY_JSON_LD_TYPES:
            continue

        same_as = item.get("sameAs")
        if isinstance(same_as, str):
            same_as = [same_as]
        elif not isinstance(same_as, list):
            same_as = []

        entities.append(
            {
                "type": types,
                "name": item.get("name"),
                "url": item.get("url"),
                "logo": item.get("logo") if isinstance(item.get("logo"), str) else None,
                "same_as": same_as[:MAX_SAMEAS_LINKS],
            }
        )
    return entities


def _extract_site_name_candidates(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Collect the site's own self-descriptions of its name from common locations."""
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    og_site_name = None
    og_tag = soup.find("meta", attrs={"property": "og:site_name"})
    if og_tag and og_tag.get("content"):
        og_site_name = og_tag["content"].strip()

    return {"title": title, "og_site_name": og_site_name}


def _extract_footer_copyright_name(page_text: str) -> Optional[str]:
    """Find a business name immediately following a copyright year notice, if any."""
    match = COPYRIGHT_NAME_PATTERN.search(page_text)
    if not match:
        return None
    name = match.group(1).strip().rstrip(".,")
    # Guard against grabbing an overly long run of trailing unrelated text.
    return name[:80] if name else None


def _extract_address_samples(page_text: str) -> List[str]:
    """Find generic street-address-shaped text (presence signal, not full parsing)."""
    samples = [m.group(0).strip() for m in ADDRESS_PATTERN.finditer(page_text)]
    seen: set[str] = set()
    unique_samples: List[str] = []
    for s in samples:
        if s not in seen:
            seen.add(s)
            unique_samples.append(s)
    return unique_samples[:MAX_ADDRESS_SAMPLES]


def run_entity_signal_checks(url: str, *, rendered_html: Optional[str] = None) -> Observation:
    """
    Collect entity-identity signals for a URL: JSON-LD entity data, the
    site's own name self-descriptions (title, og:site_name, footer
    copyright name), the registered domain, and any address-shaped text.

    If rendered_html is provided (e.g. by audit-orchestrator's shared
    render pass), it's used directly instead of fetching independently.
    """
    normalized_url = validate_and_normalize_url(url)

    if rendered_html is None:
        try:
            rendered_html = fetch_rendered_html(normalized_url)
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)
            return Observation(
                id="entity-identity-signals",
                skill="freshness-corroboration",
                category="entity_identity",
                description="Entity identity signals: JSON-LD, site name self-descriptions, domain, address text.",
                data={"checked": False, "error": f"render failed: {exc}"},
            )

    soup = BeautifulSoup(rendered_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    page_text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    json_ld_entities = _extract_json_ld_entities(rendered_html, normalized_url)
    name_candidates = _extract_site_name_candidates(soup)
    footer_name = _extract_footer_copyright_name(page_text)
    address_samples = _extract_address_samples(page_text)
    domain = urlparse(normalized_url).netloc.removeprefix("www.")

    all_same_as: List[str] = []
    for entity in json_ld_entities:
        all_same_as.extend(entity.get("same_as", []))

    return Observation(
        id="entity-identity-signals",
        skill="freshness-corroboration",
        category="entity_identity",
        description="Entity identity signals: JSON-LD, site name self-descriptions, domain, address text.",
        data={
            "checked": True,
            "error": None,
            "domain": domain,
            "json_ld_entities": json_ld_entities,
            "title": name_candidates["title"],
            "og_site_name": name_candidates["og_site_name"],
            "footer_copyright_name": footer_name,
            "same_as_links_found": all_same_as[:MAX_SAMEAS_LINKS],
            "address_pattern_samples": address_samples,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="freshness-corroboration.entity_signals",
        description="Detect entity identity signals on a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_entity_signal_checks(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())