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
> Status: placeholder — full orchestration logic (calling the three specialist
> skills, aggregating evidence, deduplication, severity/priority assignment, and
> Gemini reasoning) will be implemented in a later step.

## Output
A final JSON audit report matching the schema in
`context/PROJECT_CONTEXT.md` (site, audited_at, summary, findings[]).