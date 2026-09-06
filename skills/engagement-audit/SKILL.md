---
name: engagement-audit
description: Assesses first-screen orientation, intent-to-landing-page alignment, context retention, navigation clarity, and trust signals for a visitor arriving on a target website.
license: MIT
---

# Engagement Audit

## When to use
Called by audit-orchestrator to assess the on-site visitor experience after arrival.

## Inputs
- `url` (string, required): the website to audit.

## Procedure
1. Validate and normalize the URL (`common/url_utils.py`).
2. Render the page and extract: page `<title>`, meta description, first `<h1>`,
   and the actual visible text above the fold
   (`scripts/engagement_checks.py::run_engagement_checks`). **[DONE]**
3. Detect call-to-action links/buttons, contact/about/social links, and
   phone/email patterns (`phonenumbers` library for phone detection, after
   real-world testing showed regex-only detection was unreliable).
   **[DONE]**
4. Compute a Flesch reading-ease score over the page's visible text as a
   generic proxy for content clarity. **[DONE]**
5. Measure intent-to-landing alignment and context retention (treated as
   one measurement — see context/DECISIONS.md): ask an LLM what it
   independently knows about the site's bare domain name (no page content
   supplied, avoiding circularity), then measure word overlap between that
   independent description and the page's actual above-fold content
   (`scripts/intent_alignment.py::run_intent_alignment_check`). **[DONE]**
   If the LLM has no independent knowledge of the entity, no comparison is
   made — this is reported as `checked: true, llm_knows_entity: false`,
   not as a failure.
6. Return all findings as a list of `Observation` objects (`common/schema.py`).

## Output
A list of `Observation` objects consumed by audit-orchestrator:
`engagement-first-screen`, `engagement-trust-navigation`, and
`engagement-intent-alignment`.

Run the checks standalone with:
```
python skills/engagement-audit/scripts/engagement_checks.py <url>
python skills/engagement-audit/scripts/intent_alignment.py <url>
```