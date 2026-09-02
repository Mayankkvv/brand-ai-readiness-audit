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
             -> structured data (extruct)                [TODO]
        -> freshness-corroboration                       [TODO]
        -> engagement-audit                              [TODO]
   -> combined evidence                                  [TODO - not wired yet]
   -> Gemini reasoning                                   [TODO]
   -> finding validation / deduplication                 [TODO]
   -> severity + priority                                [TODO]
   -> AuditReport (common/schema.py)                     [DONE, empty findings only]
```