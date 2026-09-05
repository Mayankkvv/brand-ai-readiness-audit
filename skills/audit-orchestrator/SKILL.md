---
name: audit-orchestrator
description: Sole entrypoint. Receives a website URL, coordinates crawl-render-audit, freshness-corroboration, and engagement-audit, then merges their evidence into one deduplicated, prioritized, evidence-backed audit report.
license: MIT
---

# Audit Orchestrator

## When to use
This is the entrypoint skill. Invoke it directly with a target website URL to run a
full AI discoverability + engagement audit.

## Inputs
- `url` (string, required): the website to audit.
- `GEMINI_API_KEY` (environment variable, required for real findings): see
  `.env.example`. If unset, the audit still runs and returns raw
  `observations`, but `findings` will be empty.

## Procedure
1. Receive and validate the input URL (`common/url_utils.py`). **[DONE]**
2. Call crawl-render-audit, freshness-corroboration, and engagement-audit,
   passing the validated URL to each (`scripts/skill_runner.py`). **[DONE]**
   A single failing check is caught and recorded as an error Observation
   rather than crashing the whole audit.
3. Send the aggregated `Observation` list to the configured LLM provider
   (`scripts/reasoning.py::generate_findings`, backed by `llm/provider.py`).
   **[DONE]** The LLM interprets evidence already collected deterministically
   - it never invents facts and never sees raw page content beyond what's
   summarized in the observations.
4. Validate each returned finding against `common/schema.py` and assign a
   stable `id` (F-001, F-002, ...); invalid items are skipped individually
   rather than failing the whole response. **[DONE]**
5. *(not yet implemented)* Deduplicate/resolve conflicting findings across
   multiple runs or overlapping evidence.
6. Return the final `AuditReport` as JSON. **[DONE]** — `findings` and
   `summary` are now populated end-to-end.

Run it with: python skills/audit-orchestrator/scripts/cli.py <url>


**Known limitation:** each rendering-dependent check (render diff, structured
data, image OCR, engagement checks) currently opens its own independent
Playwright browser session, so one orchestrator run renders the target page
multiple times. This will be consolidated into a single shared render pass
in a dedicated runtime-optimization step.

## Output
A JSON `AuditReport` (`common/schema.py`): `site`, `audited_at`, `summary`,
`findings` (real, evidence-backed findings from LLM reasoning), and
`observations` (the raw evidence collected by the specialist skills).