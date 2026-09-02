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

## Procedure
1. Receive and validate the input URL (`common/url_utils.py`), rejecting empty or
   malformed input with a clear error. **[DONE]**
2. Call crawl-render-audit, freshness-corroboration, and engagement-audit,
   passing the validated URL to each (`scripts/skill_runner.py::run_all_specialist_skills`).
   **[DONE]**
3. Collect each skill's raw evidence as `Observation` objects, attached to the
   report's `observations` field. **[DONE]** A single failing check is caught
   and recorded as an error Observation rather than crashing the whole audit.
4. *(not yet implemented)* Normalize, deduplicate, and resolve conflicting
   findings.
5. *(not yet implemented)* Send aggregated evidence to Gemini for reasoning
   about severity, impact, and recommendations, turning Observations into
   real Findings.
6. *(not yet implemented)* Validate the final findings against
   `common/schema.py` and assemble the final `findings`/`summary` fields.
7. Return the `AuditReport` as JSON. **[DONE]** (currently with populated
   `observations` but empty `findings`, since step 5 doesn't exist yet).

Run it with:
python skills/audit-orchestrator/scripts/cli.py <url>


**Known limitation:** each rendering-dependent check (render diff, structured
data, image OCR, engagement checks) currently opens its own independent
Playwright browser session, so one orchestrator run renders the target page
multiple times. This will be consolidated into a single shared render pass
in a dedicated runtime-optimization step.

## Output
A JSON `AuditReport` (`common/schema.py`): `site`, `audited_at`, `summary`,
`findings` (currently always empty), and `observations` (the raw evidence
collected so far).