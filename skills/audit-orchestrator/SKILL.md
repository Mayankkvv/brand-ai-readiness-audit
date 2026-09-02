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
   malformed input with a clear error.
2. *(not yet implemented)* Call crawl-render-audit, freshness-corroboration, and
   engagement-audit, passing the validated URL to each.
3. *(not yet implemented)* Collect each skill's evidence/observations.
4. *(not yet implemented)* Normalize, deduplicate, and resolve conflicting findings.
5. *(not yet implemented)* Send aggregated evidence to Gemini for reasoning about
   severity, impact, and recommendations.
6. *(not yet implemented)* Validate the final findings against `common/schema.py`
   and assemble the report.
7. Return the final `AuditReport` as JSON.

**Current capability (Step 3):** step 1 and step 7 only — the CLI validates a URL
and emits an empty-findings report, proving the schema and wiring are correct.

Run it with:python skills/audit-orchestrator/scripts/cli.py <url>


## Output
A final JSON audit report matching `common/schema.py` / the schema documented in
`context/PROJECT_CONTEXT.md` (site, audited_at, summary, findings[]).