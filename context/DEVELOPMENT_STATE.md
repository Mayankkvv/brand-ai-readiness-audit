# DEVELOPMENT STATE

Current step:
Step 6 — Crawl & Render Audit: Structured Data Checks (COMPLETE)

Completed:
- Project root, Git repo, context system (Step 1)
- marketplace.json + skills/ folder skeleton (Step 2)
- Shared common/ package: schema.py (AuditReport/Finding/Observation), url_utils.py
- Working audit-orchestrator CLI producing an empty AuditReport (Step 3)
- crawl-render-audit: HTTP status/redirects, robots.txt, sitemap checks (Step 4)
- crawl-render-audit: Playwright render diff (Step 5)
- crawl-render-audit: structured data checks (JSON-LD/microdata/OpenGraph via
  extruct), comparing raw vs. rendered HTML (Step 6)
- Refactored shared fetch logic (fetch_raw_html/fetch_rendered_html) into a new
  skills/crawl-render-audit/scripts/fetchers.py, used by both render_checks.py
  and structured_data_checks.py

Current implementation:
crawl-render-audit now has three standalone scripts (access_checks.py,
render_checks.py, structured_data_checks.py), all returning Observations. None
are wired into audit-orchestrator yet. Hidden non-text fact detection (images
with important text not in HTML) is still TODO for this skill.
freshness-corroboration and engagement-audit remain placeholder-only. No Gemini
integration yet.

Known issues:
None yet. Note: structured_data_checks.py and render_checks.py each launch
their own Playwright browser instance independently, so running both against
the same URL currently renders the page twice - the orchestrator will later
consolidate this into a single render pass for runtime efficiency.

- (Fixed, Step 9) fetch_utils.py originally waited for Playwright's
  "networkidle" state, which timed out on real sites with continuous
  background network activity (e.g. python.org). Switched all three
  rendering functions to wait for "load" plus a short fixed settle delay.

Last successful test:
`python skills\crawl-render-audit\scripts\structured_data_checks.py https://example.com`
returns a single Observation with raw/rendered structured-data summaries.

Last Git commit:
"Step 6: structured data checks + shared fetchers module" — pending push.