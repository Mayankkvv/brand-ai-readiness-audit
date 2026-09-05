# ARCHITECTURE (as actually implemented)

## Shared code
`common/` (project root - skill folder names contain hyphens and aren't valid
Python package names, so shared code lives outside `skills/`):
- `common/schema.py` — Pydantic models: Severity, Priority, SuggestedAction,
  Finding, Observation, Summary, AuditReport (with `recompute_summary()`).
- `common/url_utils.py` — `validate_and_normalize_url(raw_url) -> str`.
- `common/fetch_utils.py` — shared fetch helpers:
  - `fetch_raw_html()` / `fetch_rendered_html()` — simple one-shot fetches.
  - `rendered_browser_session()` — context manager yielding
    (rendered_html, browser_context), so callers can fetch additional
    resources (e.g. images) through the same browser context (needed
    because some CDNs block bare HTTP clients but serve real browser
    sessions fine).
  - `rendered_page_session()` — context manager yielding a live Playwright
    Page at a fixed viewport, so callers can run `page.evaluate()` to
    inspect actual rendered layout (e.g. what's visible above the fold).

## audit-orchestrator (entrypoint)
`skills/audit-orchestrator/scripts/`:
- `skill_runner.py::run_all_specialist_skills()` — runs access_checks
  independently (no rendering needed), then opens ONE shared
  `common.fetch_utils.full_render_session()` and passes its raw_html/
  rendered_html/above_fold_text/context to render_checks,
  structured_data_checks, image_checks, date_signals, and
  engagement_checks - each still individually fault-isolated. If the
  shared render itself fails, all 5 become error Observations.
- `reasoning.py::generate_findings()` — sends aggregated Observations to
  the LLM, validates/normalizes the response into Findings.
- `cli.py::run_audit()` — validates the URL, runs skill_runner, runs
  reasoning, assembles the final AuditReport.

## llm/ (modular LLM provider layer)
`llm/provider.py` — `LLMProvider` abstract interface + `get_provider()` factory.
`llm/gemini.py` — `GeminiProvider`, using `google-genai`. Forces
`GOOGLE_API_KEY` to match the configured key (fixes an SDK ambient-env-var
conflict found via testing) and retries transient errors (503/429-style)
with backoff before giving up.

`llm/gemini.py`:
- `GeminiProvider` — implements `LLMProvider` using Google's `google-genai`
  SDK (the current, actively maintained package - NOT the deprecated
  `google-generativeai`). Requests JSON output via
  `GenerateContentConfig(response_mime_type="application/json")`.

`skills/audit-orchestrator/scripts/reasoning.py`:
- `generate_findings(site, observations) -> List[Finding]` — builds one
  combined prompt from all aggregated Observations, calls the configured
  LLM provider once, parses/validates the JSON response into `Finding`
  objects (via a local `_FindingDraft` Pydantic model), assigns stable
  `F-001`-style ids, and normalizes severity/priority casing defensively.
  Any failure (missing API key, LLM error, unparseable response, invalid
  individual findings) degrades gracefully rather than raising.

## crawl-render-audit (feature-complete, shares one render with other skills)
`skills/crawl-render-audit/scripts/`:
- `access_checks.py` — HTTP status/redirects, robots.txt, sitemap (no rendering).
- `render_checks.py` — raw vs. rendered visible-text diff. Accepts optional
  pre-fetched raw_html/rendered_html.
- `structured_data_checks.py` — JSON-LD/microdata/OpenGraph via `extruct`.
  Accepts optional pre-fetched raw_html/rendered_html.
- `image_checks.py` — OCRs content images via Tesseract. Accepts optional
  pre-rendered rendered_html/context.

## freshness-corroboration (in progress)
`skills/freshness-corroboration/scripts/date_signals.py` — date/freshness
signals. Accepts optional pre-rendered rendered_html.
TODO: claim consistency, external corroboration, entity ambiguity.

## engagement-audit (in progress)
`skills/engagement-audit/scripts/engagement_checks.py` — first-screen
orientation, CTA/trust/navigation signals (phone detection via
`phonenumbers`), readability. Accepts optional pre-rendered
rendered_html/above_fold_text.
TODO: intent-to-landing alignment, context retention.

## Shared render architecture (Step 12)
`common/fetch_utils.py::full_render_session()` performs ONE Playwright
render per audited URL and yields a `RenderResult` (raw_html, rendered_html,
above_fold_text, live browser context). audit-orchestrator uses this to run
all 5 rendering-dependent checks against a single render. Each script's
standalone CLI still uses its own independent render
(`fetch_rendered_html()`/`rendered_browser_session()`/`rendered_page_session()`),
unchanged.

## Target end-to-end flow
```
Website URL
   -> audit-orchestrator/scripts/cli.py
        -> validate_and_normalize_url()                    [DONE]
        -> skill_runner.run_all_specialist_skills()
             -> access_checks (independent)                 [DONE]
             -> ONE shared full_render_session()             [DONE - Step 12]
                  -> render_checks                            [DONE]
                  -> structured_data_checks                    [DONE]
                  -> image_checks                               [DONE]
                  -> date_signals                                [DONE]
                  -> engagement_checks                            [DONE]
        -> reasoning.generate_findings() (Gemini)               [DONE]
   -> AuditReport (findings + summary + observations)            [DONE]
```