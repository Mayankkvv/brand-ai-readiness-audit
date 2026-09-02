# ARCHITECTURE (as actually implemented)

## Shared code
`common/` (project root - skill folder names contain hyphens and aren't valid
Python package names, so shared code lives outside `skills/`):
- `common/schema.py` — Pydantic models: Severity, Priority, SuggestedAction,
  Finding, Observation, Summary, AuditReport (with `recompute_summary()`).
- `common/url_utils.py` — `validate_and_normalize_url(raw_url) -> str`.
- `common/fetch_utils.py` — shared `fetch_raw_html()` / `fetch_rendered_html()`
  helpers (httpx + Playwright/Chromium). Originally lived inside
  crawl-render-audit's scripts/fetchers.py (Step 6); moved to common/ in
  Step 8 once freshness-corroboration also needed identical fetch logic.

## audit-orchestrator (entrypoint)
`skills/audit-orchestrator/scripts/cli.py`:
- Adds project root to `sys.path` so it can import `common`.
- Validates the input URL.
- Currently builds and prints an empty-findings `AuditReport` as JSON.
- Not yet implemented: calling the three specialist skills, evidence aggregation,
  deduplication, Gemini reasoning, final validation.

## crawl-render-audit (feature-complete)
`skills/crawl-render-audit/scripts/`:
- `access_checks.py::run_access_checks()` — HTTP status/redirects, robots.txt
  (disallowed paths + declared sitemaps), sitemap discovery/parsing.
- `render_checks.py::run_render_checks()` — raw HTML vs. rendered DOM visible
  text: word-count delta, % increase, difflib similarity ratio. Also exposes
  `extract_visible_text()`, reused by image_checks.py.
- `structured_data_checks.py::run_structured_data_checks()` — JSON-LD/
  microdata/OpenGraph via `extruct`, compared raw vs. rendered, flags whether
  JSON-LD only appears after rendering.
- `image_checks.py::run_image_text_checks()` — OCRs up to 8 largest
  content-sized `<img>` tags (filtering icons/logos/tracking pixels), reports
  word-overlap ratio between each image's text and the page's visible text.
- All four import shared fetch helpers from `common/fetch_utils.py`.

## freshness-corroboration (in progress)
`skills/freshness-corroboration/scripts/`:
- `date_signals.py::run_date_signal_checks()` — extracts date/freshness
  signals: known `<meta>` date tags, JSON-LD `datePublished`/`dateModified`,
  visible "last updated"/"published on" text patterns (regex), and
  copyright-year notices; reports gap between latest copyright year and the
  current year as a raw number (not a verdict).
- TODO: claim consistency across pages, external corroboration, entity
  ambiguity assessment (likely needs Gemini reasoning, not pure determinism).

## engagement-audit (not started)
SKILL.md placeholder only, no scripts yet.

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
        -> engagement-audit                                [TODO]
   -> combined evidence                                    [TODO - not wired yet]
   -> Gemini reasoning                                     [TODO]
   -> finding validation / deduplication                   [TODO]
   -> severity + priority                                  [TODO]
   -> AuditReport (common/schema.py)                       [DONE, empty findings only]
```