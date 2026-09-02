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
- `skill_runner.py::run_all_specialist_skills()` — dynamically loads each
  specialist skill's script module by file path (via `importlib.util`,
  since skill folder names contain hyphens and aren't valid Python package
  names), calls its check function(s), and aggregates every returned
  `Observation` into one list. Each check is individually wrapped so a
  failure becomes an error Observation instead of crashing the run.
- `cli.py::run_audit()` — validates the URL, calls `run_all_specialist_skills()`,
  and assembles an `AuditReport` with the collected `observations` (findings
  still empty - no Gemini reasoning layer yet).
- Not yet implemented: deduplication, Gemini reasoning, severity/priority
  assignment, final Finding validation.

## crawl-render-audit (feature-complete, hardened)
`skills/crawl-render-audit/scripts/`:
- `access_checks.py` — HTTP status/redirects, robots.txt, sitemap.
- `render_checks.py` — raw vs. rendered visible-text diff (word count,
  similarity ratio). Exposes `extract_visible_text()`, reused by
  image_checks.py.
- `structured_data_checks.py` — JSON-LD/microdata/OpenGraph via `extruct`,
  raw vs. rendered.
- `image_checks.py` — OCRs up to 8 content-sized images (filtering icons,
  SVGs, duplicate URLs), reports word-overlap vs. page text. Downloads via
  `rendered_browser_session()` to avoid CDN 403s on bare HTTP requests.

## freshness-corroboration (in progress)
`skills/freshness-corroboration/scripts/`:
- `date_signals.py` — meta date tags, JSON-LD dates, visible "last
  updated" text patterns, copyright-year gap.
- TODO: claim consistency across pages, external corroboration, entity
  ambiguity (likely needs Gemini reasoning).

## engagement-audit (in progress)
`skills/engagement-audit/scripts/`:
- `engagement_checks.py::run_engagement_checks()` — returns two
  Observations:
  - `engagement-first-screen` — title, meta description, first H1, actual
    above-fold visible text (via `rendered_page_session()` + JS layout
    query), and a Flesch reading-ease readability score.
  - `engagement-trust-navigation` — CTA link/button detection (generic
    action-verb keyword matching), contact/about link presence, social
    profile link detection, phone/email pattern detection.
- TODO: intent-to-landing alignment and context retention - both need an
  "assumed user intent" input that no caller currently supplies (will come
  from the orchestrator once it's wired to pass AI-answer context through).

## Target end-to-end flow
```
Website URL
   -> audit-orchestrator/scripts/cli.py
        -> validate_and_normalize_url()               [DONE]
        -> crawl-render-audit
             -> HTTP status / redirects                [DONE]
             -> robots.txt                              [DONE]
             -> sitemap discovery/parsing                [DONE]
             -> Playwright render diff                   [DONE]
             -> structured data (extruct)                [DONE]
             -> hidden image-text detection (OCR)         [DONE]
        -> freshness-corroboration
             -> date/freshness signal detection          [DONE]
             -> claim consistency / corroboration         [TODO]
             -> entity ambiguity                           [TODO]
        -> engagement-audit
             -> first-screen orientation                  [DONE]
             -> CTA / navigation detection                 [DONE]
             -> trust signal detection                      [DONE]
             -> readability (content clarity)                [DONE]
             -> intent-to-landing alignment                    [TODO - needs assumed intent input]
             -> context retention                              [TODO - needs assumed intent input]
   -> combined evidence                                    [DONE - AuditReport.observations]
   -> Gemini reasoning                                     [TODO]
   -> finding validation / deduplication                   [TODO]
   -> severity + priority                                  [TODO]
   -> AuditReport (common/schema.py)                       [DONE - findings still always empty]
```