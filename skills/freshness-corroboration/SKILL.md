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

## Procedure
1. Validate and normalize the URL (`common/url_utils.py`).
2. Detect date/freshness signals: `<meta>` tags (article:published_time,
   article:modified_time, etc.), JSON-LD `datePublished`/`dateModified`,
   visible "last updated"/"published on" text patterns, and copyright-year
   notices (`scripts/date_signals.py::run_date_signal_checks`). **[DONE]**
   Per the project's guidance, absence of a date signal is reported as a fact
   only — it is evidence of lower transparency, not proof the content is
   stale; that judgment is made later.
3. *(not yet implemented)* Identify important factual claims (company name,
   leadership, pricing, locations, policies, etc.) and check internal
   consistency across pages.
4. *(not yet implemented)* Check corroboration of key claims against
   independent sources, distinguishing "no corroboration found" from "direct
   contradiction found."
5. *(not yet implemented)* Assess entity clarity/ambiguity (can a machine
   confidently determine which entity this website represents?).
6. Return all findings as a list of `Observation` objects (`common/schema.py`).

## Output
A list of `Observation` objects to be consumed by audit-orchestrator.

Run the checks standalone with:
```
python skills/freshness-corroboration/scripts/date_signals.py <url>
```