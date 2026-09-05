"""
Gemini reasoning layer for audit-orchestrator.

Sends the full set of aggregated Observations to the configured LLM
provider (llm/provider.py) and asks it to produce a small number of high
quality, evidence-backed Findings, following the Adobe brief's rules:
evidence required, avoid false positives, prefer fewer/stronger findings,
and never invent evidence beyond what the observations actually contain.

The LLM only ever sees the structured facts already collected
deterministically by the specialist skills - it does not crawl anything
itself and cannot add facts that aren't grounded in an observation's data.

If the LLM is unavailable (no API key configured), the call fails, or its
response can't be parsed/validated, reasoning degrades gracefully: a
warning is logged and an empty findings list is returned rather than
crashing the audit. Observations remain visible in the report either way.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.schema import Finding, Observation, Severity, SuggestedAction  # noqa: E402
from llm.provider import ProviderConfigError, get_provider  # noqa: E402

logger = logging.getLogger("audit-orchestrator.reasoning")

MAX_FINDINGS = 10

SYSTEM_INSTRUCTION = """You are an expert auditor assessing a website for two things:
1. AI discoverability - why AI assistants/search systems might fail to find,
   understand, trust, or correctly cite this website or its information.
2. On-site engagement - why a visitor arriving on this website might fail to
   understand the page, retain context, or continue engaging.

You will be given a list of Observations: raw, deterministic measurements
already collected about the site (HTTP/robots/sitemap status, raw-vs-rendered
content differences, structured data, image text detection, date/freshness
signals, first-screen orientation, CTA/trust signals, readability). These are
facts, not judgments - your job is to decide which of them represent a real,
evidence-backed problem worth reporting as a Finding.

Critical rules:
- NEVER invent a fact that isn't present in the observation data you were given.
- An observation is not automatically a problem. For example: using JavaScript
  is not a problem by itself - only report it if content that matters is
  genuinely missing from crawlable HTML. Missing structured data is not
  automatically bad - only report it if it's clearly relevant to the page.
  A missing date is evidence of lower transparency, not proof of staleness.
- Prefer FEWER, STRONGER findings over many generic ones. Return at most
  8 findings. If the evidence doesn't support any real problem, return an
  empty JSON array - do not invent a finding just to have something to say.
- Every finding's "evidence" field must cite specific facts/numbers actually
  present in the observations (URLs, counts, ratios, sample text, etc.).
- Do not flag an observation that already succeeded with no notable gap
  (e.g. checked=true and no red flags in the data).

Return ONLY a JSON array (no markdown, no code fences, no commentary before
or after it). Each array item must be an object with exactly these fields:
- "title": short string
- "severity": one of "critical", "high", "medium", "low", "informational"
- "evidence": string citing specific facts from the observations
- "suggested_action": object with "summary" (string) and "priority" (one of
  "critical", "high", "medium", "low")
- "category": short string (optional)
- "confidence": number between 0 and 1 (optional)

If there is nothing substantial to report, return: []
"""


class _FindingDraft(BaseModel):
    """Validated shape of a single finding the LLM returned, before we assign it a final id."""

    title: str
    severity: Severity
    evidence: str
    suggested_action: SuggestedAction
    category: Optional[str] = None
    confidence: Optional[float] = None


def _build_user_prompt(site: str, observations: List[Observation]) -> str:
    obs_json = json.dumps([o.model_dump() for o in observations], indent=2)
    return (
        f"Website audited: {site}\n\n"
        f"Observations collected (raw evidence, not yet judged):\n{obs_json}\n\n"
        "Analyze these observations and return findings following your instructions."
    )


def _normalize_enum_casing(item: Dict[str, Any]) -> Dict[str, Any]:
    """Defensively lowercase severity/priority strings in case the LLM capitalizes them."""
    if isinstance(item.get("severity"), str):
        item["severity"] = item["severity"].strip().lower()
    action = item.get("suggested_action")
    if isinstance(action, dict) and isinstance(action.get("priority"), str):
        action["priority"] = action["priority"].strip().lower()
    return item


def _parse_findings(raw_text: str) -> List[Finding]:
    """Parse and validate the LLM's raw text response into a list of Findings."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc

    if not isinstance(items, list):
        raise ValueError("LLM response JSON was not a list of findings.")

    findings: List[Finding] = []
    for index, item in enumerate(items[:MAX_FINDINGS]):
        if not isinstance(item, dict):
            logger.warning("Skipping non-object finding at index %d.", index)
            continue
        try:
            draft = _FindingDraft.model_validate(_normalize_enum_casing(item))
        except ValidationError as exc:
            logger.warning("Skipping invalid finding at index %d: %s", index, exc)
            continue
        findings.append(
            Finding(
                id=f"F-{len(findings) + 1:03d}",
                title=draft.title,
                severity=draft.severity,
                evidence=draft.evidence,
                suggested_action=draft.suggested_action,
                category=draft.category,
                confidence=draft.confidence,
            )
        )
    return findings


def generate_findings(site: str, observations: List[Observation]) -> List[Finding]:
    """Turn aggregated Observations into real, evidence-backed Findings via LLM reasoning."""
    try:
        provider = get_provider()
    except ProviderConfigError as exc:
        logger.warning("LLM reasoning skipped: %s", exc)
        return []

    user_prompt = _build_user_prompt(site, observations)

    try:
        raw_response = provider.generate_json(SYSTEM_INSTRUCTION, user_prompt)
    except Exception as exc:  # noqa: BLE001 - an LLM failure must not crash the audit
        logger.warning("LLM call failed: %s", exc)
        return []

    try:
        return _parse_findings(raw_response)
    except ValueError as exc:
        logger.warning("Could not parse LLM findings: %s", exc)
        return []