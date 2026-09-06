"""
Intent-to-landing-page alignment for the engagement-audit skill.

Covers the two remaining planned areas from the brief - intent-to-landing
alignment and context retention - which are treated as one measurement
here (both ask essentially the same question: "does this page reinforce
what a visitor was led to expect?"), documented as a deliberate
consolidation in context/DECISIONS.md rather than two near-duplicate
checks.

This requires a genuinely INDEPENDENT assumption of what an AI assistant
would tell a visitor about this site - never one derived from the page's
own content, which would be circular (a page can never "misalign" with a
guess pulled from itself; see Step 9's decision log). So this asks Gemini
what it already knows about the site's bare DOMAIN NAME ONLY, from its own
training knowledge, with no page content supplied - honestly declining if
it doesn't recognize the entity rather than guessing.

This is still a pure Observation (a measured word-overlap ratio) - whether
a low overlap represents a real problem is judged later by
audit-orchestrator's main reasoning call, which receives this evidence
alongside everything else.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.fetch_utils import ABOVE_FOLD_TEXT_JS, rendered_page_session  # noqa: E402
from common.schema import Observation  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402
from llm.provider import ProviderConfigError, get_provider  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("engagement-audit.intent_alignment")

MAX_ASSUMED_INTENT_CHARS = 500

SYSTEM_INSTRUCTION = """You are simulating what an AI assistant would tell a user, from
your own general training knowledge only (no browsing, no page content provided),
if asked to briefly describe a specific website/company/product identified only by
its domain name below.

Return ONLY a JSON object with exactly these fields:
- "known_entity": boolean - true ONLY if you have specific, reliable prior knowledge
  of this exact entity (not a generic guess based on how the domain name sounds).
- "assumed_intent": string - if known_entity is true, a 1-2 sentence plain-language
  description of what this entity does or offers, in the style of a brief AI
  assistant answer. If known_entity is false, an empty string.

Be honest and conservative: if the domain is generic, obscure, or you are not
confident you know this specific entity, set known_entity to false rather than
guessing. Do not fabricate details.
"""


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.")


def _query_assumed_intent(domain: str) -> dict:
    """
    Ask Gemini what it independently knows about `domain`, with no page
    content supplied. Returns {"known_entity": bool, "assumed_intent": str}.
    Raises on provider/parsing failure - caller handles graceful fallback.
    """
    provider = get_provider()
    user_prompt = f"Domain: {domain}\n\nWhat do you know about this entity?"
    raw_text = provider.generate_json(SYSTEM_INSTRUCTION, user_prompt)

    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Assumed-intent response was not a JSON object.")

    known_entity = bool(parsed.get("known_entity", False))
    assumed_intent = str(parsed.get("assumed_intent", "")).strip()[:MAX_ASSUMED_INTENT_CHARS]
    return {"known_entity": known_entity, "assumed_intent": assumed_intent}


def _word_overlap_ratio(assumed_intent_text: str, above_fold_text: str) -> float:
    """Fraction of distinct assumed-intent words that also appear in above-fold text."""
    intent_words = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", assumed_intent_text)}
    if not intent_words:
        return 0.0
    page_words = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", above_fold_text)}
    matched = intent_words & page_words
    return round(len(matched) / len(intent_words), 3)


def run_intent_alignment_check(
    url: str,
    *,
    rendered_html: Optional[str] = None,
    above_fold_text: Optional[str] = None,
) -> Observation:
    """
    Measure alignment between an independently-sourced assumption of what
    this site is about and its actual above-fold content.

    If rendered_html/above_fold_text are provided (e.g. by
    audit-orchestrator's shared render pass), they are used directly
    instead of opening a separate Playwright session.
    """
    normalized_url = validate_and_normalize_url(url)
    domain = _extract_domain(normalized_url)

    if rendered_html is None or above_fold_text is None:
        try:
            with rendered_page_session(normalized_url) as page:
                rendered_html = page.content()
                above_fold_text = page.evaluate(ABOVE_FOLD_TEXT_JS)
        except PlaywrightError as exc:
            logger.warning("Rendering failed for %s: %s", normalized_url, exc)
            return Observation(
                id="engagement-intent-alignment",
                skill="engagement-audit",
                category="engagement",
                description="Alignment between an independent assumption of site intent and above-fold content.",
                data={"checked": False, "error": f"render failed: {exc}"},
            )

    try:
        intent_result = _query_assumed_intent(domain)
    except ProviderConfigError as exc:
        logger.warning("Intent alignment skipped: %s", exc)
        return Observation(
            id="engagement-intent-alignment",
            skill="engagement-audit",
            category="engagement",
            description="Alignment between an independent assumption of site intent and above-fold content.",
            data={"checked": False, "error": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001 - LLM/parsing failure must not crash the audit
        logger.warning("Intent alignment LLM call failed: %s", exc)
        return Observation(
            id="engagement-intent-alignment",
            skill="engagement-audit",
            category="engagement",
            description="Alignment between an independent assumption of site intent and above-fold content.",
            data={"checked": False, "error": f"LLM call failed: {exc}"},
        )

    if not intent_result["known_entity"]:
        return Observation(
            id="engagement-intent-alignment",
            skill="engagement-audit",
            category="engagement",
            description="Alignment between an independent assumption of site intent and above-fold content.",
            data={
                "checked": True,
                "error": None,
                "domain": domain,
                "llm_knows_entity": False,
                "assumed_intent_text": None,
                "above_fold_word_overlap_ratio": None,
                "note": "The LLM reported no independent prior knowledge of this entity, "
                        "so no alignment comparison could be made.",
            },
        )

    overlap_ratio = _word_overlap_ratio(intent_result["assumed_intent"], above_fold_text)

    return Observation(
        id="engagement-intent-alignment",
        skill="engagement-audit",
        category="engagement",
        description="Alignment between an independent assumption of site intent and above-fold content.",
        data={
            "checked": True,
            "error": None,
            "domain": domain,
            "llm_knows_entity": True,
            "assumed_intent_text": intent_result["assumed_intent"],
            "above_fold_word_overlap_ratio": overlap_ratio,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="engagement-audit.intent_alignment",
        description="Measure intent-to-landing-page alignment for a website.",
    )
    parser.add_argument("url", help="Website URL to check, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        observation = run_intent_alignment_check(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    print(json.dumps(observation.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())