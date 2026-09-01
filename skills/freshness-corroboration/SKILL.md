---
name: freshness-corroboration
description: Identifies stale or conflicting important facts, checks corroboration against independent sources, and assesses entity clarity/ambiguity on a target website.
license: MIT
---

# Freshness & Corroboration

## When to use
Called by audit-orchestrator to assess factual freshness, consistency, and entity
clarity of a website.

## Inputs
- `url` (string, required): the website to audit.
- Evidence already collected by crawl-render-audit (facts, dates, structured data),
  where available.

## Procedure
> Status: placeholder — checks for staleness signals, internal consistency, external
> corroboration, and entity ambiguity will be implemented in a later step.

## Output
A list of evidence-backed observations about factual freshness, consistency, and
entity clarity, to be consumed by audit-orchestrator.