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
- `assumed_user_intent` (string, optional — not yet supported): what an AI
  assistant told the visitor before they arrived, e.g. "Company X provides
  AI customer-support software." Needed for intent-alignment and
  context-retention checks; those checks are not yet implemented because no
  caller currently supplies this input (see Procedure, steps 3-4).

## Procedure
1. Validate and normalize the URL (`common/url_utils.py`).
2. Render the page at a fixed viewport and extract: page `<title>`, meta
   description, first `<h1>`, and the actual visible text above the fold
   (via live DOM layout, not just raw HTML order)
   (`scripts/engagement_checks.py::run_engagement_checks`). **[DONE]**
3. *(not yet implemented)* Compare the above-fold content against an assumed
   AI-answer intent to assess intent-to-landing-page alignment. Requires the
   `assumed_user_intent` input, which no caller currently provides.
4. *(not yet implemented)* Assess context retention (does the page reinforce
   "yes, this is what I was looking for" for a visitor arriving with prior
   context). Same dependency as step 3.
5. Detect call-to-action links/buttons using generic action-verb patterns
   (`scripts/engagement_checks.py::_find_cta_elements`). **[DONE]**
6. Detect trust/navigation signals: contact/about links, social profile
   links, visible phone/email patterns
   (`scripts/engagement_checks.py::_find_trust_navigation_signals`). **[DONE]**
7. Compute a Flesch reading-ease score over the page's visible text as a
   generic proxy for content clarity
   (`scripts/engagement_checks.py::_compute_readability`). **[DONE]** A low
   score is a measurement, not automatically a problem — appropriate
   reading level varies by audience and page type, which is judged later.
8. Return all findings as a list of `Observation` objects (`common/schema.py`).

## Output
A list of `Observation` objects to be consumed by audit-orchestrator:
`engagement-first-screen` (title/meta/H1/above-fold text/readability) and
`engagement-trust-navigation` (CTAs, contact/about/social links, phone/email
patterns).

Run the checks standalone with:
```
python skills/engagement-audit/scripts/engagement_checks.py <url>
```