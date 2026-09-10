# TESTING

## Automated tests (pytest)
Added Step 15. Run with `pytest` from the project root - fast (no network,
browser, or LLM calls), covers pure/deterministic logic only:
- `tests/common/test_url_utils.py` — URL validation/normalization
- `tests/common/test_schema.py` — AuditReport summary computation
- `tests/crawl_render_audit/test_render_checks.py` — visible-text
  extraction, raw-vs-rendered diff computation
- `tests/engagement_audit/test_engagement_checks.py` — page metadata
  extraction, CTA detection, readability scoring, and phone-number
  detection (including explicit regressions for the 3 real false
  positives found via manual testing - see below)
- `tests/audit_orchestrator/test_reasoning.py` — LLM JSON response
  parsing, markdown-fence stripping, per-item validation, enum-casing
  normalization

NOT covered by automated tests (manually tested only): anything requiring
live HTTP/Playwright/Tesseract/Gemini - i.e. most of the actual per-check
`run_*()` functions across all three specialist skills, and the real
orchestrator/reasoning end-to-end flow.

## Manual tests performed (chronological, via real CLI runs)
- example.com — used repeatedly as the minimal/edge-case baseline across
  every skill (empty robots.txt/sitemap, no structured data, no images,
  no CTAs - confirms checks report "not found" correctly rather than
  erroring).
- en.wikipedia.org (disambiguation page and Python programming language
  article) — surfaced and led to fixing: CDN 403s on direct image
  downloads (now via browser context), SVG decode errors, duplicate
  candidate image URLs, HTTP 429 rate limiting behavior (confirmed
  graceful, not a bug).
- www.python.org — the primary real-world integration test site.
  Surfaced and led to fixing: Playwright "networkidle" timeout
  unreliability (switched to "load" + settle delay), Gemini API key
  ambiguity (GOOGLE_API_KEY vs GEMINI_API_KEY), a wrong default Gemini
  model name (404), three rounds of phone-number false positives (a
  float, a date stamp, a Fibonacci sequence - ultimately fixed by
  switching to the `phonenumbers` library), a transient Gemini 503
  (added retry-with-backoff), and confirmed the Step 12 render
  consolidation actually eliminated the intermittent per-check timeouts
  it was built to fix (~23s full audit, no timeouts, on a later run).

## Websites tested against for research/pattern purposes
Not yet done systematically - see NEXT_STEPS.md item for testing against
Apple, Nike, Samsung, Notion, HubSpot, MIT, Stanford, Marriott, Reuters,
and comparable smaller sites, to validate generalization before final
submission.

## Bugs discovered and fixed
Full technical detail and reasoning for each fix is in context/DECISIONS.md
(searchable by "Decision:") and context/DEVELOPMENT_STATE.md's "Known
issues" sections at the step they were fixed. This file tracks WHAT was
tested and found; DECISIONS.md tracks WHY each fix was made the way it was.