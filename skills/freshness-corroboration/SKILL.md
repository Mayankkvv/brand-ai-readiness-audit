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
2. Detect date/freshness signals: `<meta>` tags, JSON-LD `datePublished`/
   `dateModified`, visible "last updated" text, copyright-year notices
   (`scripts/date_signals.py::run_date_signal_checks`). **[DONE]**
3. Collect entity identity signals: JSON-LD Organization/LocalBusiness data
   (name, url, logo, `sameAs` links), the site's own name self-descriptions
   (title, `og:site_name`, footer copyright name), its domain, and any
   address-shaped text (`scripts/entity_signals.py::run_entity_signal_checks`).
   **[DONE]** This is raw evidence only — whether the collected names/domain
   are actually consistent or ambiguous is judged later by audit-orchestrator's
   Gemini reasoning stage, which receives this alongside every other skill's
   evidence in the same single reasoning call (no separate LLM call needed
   for this skill).
4. *(explicitly out of scope for now)* Checking claims against independent
   external sources (live web search for corroboration/contradiction) is
   not implemented — it would require additional LLM/search calls per
   audit, working against the 5-minute runtime and free-tier rate-limit
   constraints. This is a documented scope decision, not a gap to silently
   fill later without discussion (see context/DECISIONS.md).
5. Return all findings as a list of `Observation` objects (`common/schema.py`).

## Output
A list of `Observation` objects consumed by audit-orchestrator:
`freshness-date-signals` and `entity-identity-signals`.

Run the checks standalone with:
```
python skills/freshness-corroboration/scripts/date_signals.py <url>
python skills/freshness-corroboration/scripts/entity_signals.py <url>
```