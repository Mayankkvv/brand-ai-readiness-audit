# ARCHITECTURE (as actually implemented)

## Shared code
`common/` (project root, not under skills/, because skill folder names contain
hyphens and aren't valid Python package names):
- `common/schema.py` — Pydantic models: Severity, Priority, SuggestedAction,
  Finding, Summary, AuditReport (with `recompute_summary()`).
- `common/url_utils.py` — `validate_and_normalize_url(raw_url) -> str`.

## audit-orchestrator (entrypoint)
`skills/audit-orchestrator/scripts/cli.py`:
- Adds project root to `sys.path` so it can import `common`.
- Validates the input URL.
- Currently builds and prints an empty-findings `AuditReport` as JSON.
- Not yet implemented: calling the three specialist skills, evidence aggregation,
  deduplication, Gemini reasoning, final validation.

## Specialist skills (not yet implemented)
`crawl-render-audit`, `freshness-corroboration`, `engagement-audit` — SKILL.md
placeholders only, no scripts yet.

## Target end-to-end flow
```
Website URL
   -> audit-orchestrator/scripts/cli.py
        -> validate_and_normalize_url()          [DONE]
        -> crawl-render-audit                    [TODO]
        -> freshness-corroboration                [TODO]
        -> engagement-audit                       [TODO]
   -> combined evidence                           [TODO]
   -> Gemini reasoning                            [TODO]
   -> finding validation / deduplication          [TODO]
   -> severity + priority                         [TODO]
   -> AuditReport (common/schema.py)              [DONE, empty findings only]
```