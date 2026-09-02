# ARCHITECTURE (as actually implemented)

## Shared code
`common/` (project root - skill folder names contain hyphens and aren't valid
Python package names, so shared code lives outside `skills/`):
- `common/schema.py` — Pydantic models: Severity, Priority, SuggestedAction,
  Finding, Observation, Summary, AuditReport (with `recompute_summary()`).
- `common/url_utils.py` — `validate_and_normalize_url(raw_url) -> str`.

## audit-orchestrator (entrypoint)
`skills/audit-orchestrator/scripts/cli.py`:
- Adds project root to `sys.path` so it can import `common`.
- Validates the input URL.
- Currently builds and prints an empty-findings `AuditReport` as JSON.
- Not yet implemented: calling the three specialist skills, evidence aggregation,
  deduplication, Gemini reasoning, final validation.

## crawl-render-audit
`skills/crawl-render-audit/scripts/access_checks.py`:
- `check_http_status()` — status code + redirect chain via httpx.
- `fetch_robots_txt()` — existence, disallowed paths, declared sitemaps.
- `discover_sitemap()` — tries robots-declared sitemaps, falls back to
  `/sitemap.xml`, parses URL count + sample URLs via `xml.etree.ElementTree`.
- `run_access_checks(url)` — runs all three and returns `List[Observation]`.
- Runs standalone via CLI; not yet called by audit-orchestrator.
- TODO: Playwright rendering diff, structured data (extruct) checks, hidden
  non-text fact detection.
- `render_checks.py::run_render_checks()` — fetches raw HTML (httpx) and
  rendered HTML (Playwright/Chromium), extracts visible text from each via
  BeautifulSoup, and reports word-count delta, % increase, and a difflib
  similarity ratio as a single Observation.
- `fetchers.py` — shared `fetch_raw_html()` / `fetch_rendered_html()` helpers,
  used by both render_checks.py and structured_data_checks.py (introduced in
  Step 6 to avoid duplicating fetch logic within this skill).
- `structured_data_checks.py::run_structured_data_checks()` — extracts
  JSON-LD/microdata/OpenGraph via `extruct` from both raw and rendered HTML,
  reports counts + declared schema.org types, and flags whether JSON-LD only
  appears after rendering.
- `image_checks.py::run_image_text_checks()` — finds content-sized `<img>` tags
  (filtering out icons/logos/tracking pixels by filename and dimensions), OCRs
  up to 8 of the largest via Tesseract/pytesseract, and reports word-overlap
  ratio between each image's extracted text and the page's visible text.

**crawl-render-audit is now feature-complete** (all four planned checks
implemented). Remaining work: wiring into audit-orchestrator.

## Specialist skills (remaining)
`freshness-corroboration`, `engagement-audit` — SKILL.md placeholders only, no
scripts yet.

## Target end-to-end flow
```
Website URL
   -> audit-orchestrator/scripts/cli.py
        -> validate_and_normalize_url()               [DONE]
        -> crawl-render-audit
             -> HTTP status / redirects                [DONE]
             -> robots.txt                              [DONE]
             -> sitemap discovery/parsing                [DONE]
             -> Playwright render diff                   [TODO]
             -> structured data (extruct)                [DONE]
             -> hidden image-text detection (OCR)        [DONE]
        -> freshness-corroboration                       [TODO]
        -> engagement-audit                              [TODO]
   -> combined evidence                                  [TODO - not wired yet]
   -> Gemini reasoning                                   [TODO]
   -> finding validation / deduplication                 [TODO]
   -> severity + priority                                [TODO]
   -> AuditReport (common/schema.py)                     [DONE, empty findings only]
```