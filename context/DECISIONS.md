# DECISIONS

Decision: Use Python as the primary implementation language.
Reason: Required/recommended by Adobe brief; strong ecosystem for crawling, parsing,
and LLM orchestration.

Decision: Use Playwright for rendering rather than Selenium.
Reason: Faster, better modern API, reliable headless rendering for raw-vs-rendered
HTML comparison.

Decision: Use Google Gemini API as the initial LLM provider, behind a modular
llm/provider.py interface.
Reason: Free tier available for development; brief requires provider-neutrality, so
the interface must allow swapping providers later without rewriting audit logic.

Decision: Development happens on Windows; all commands given in PowerShell.
Reason: Matches the developer's actual environment.


Decision: Create a top-level `common/` package (outside `skills/`) for the Pydantic
report schema and URL validation utilities.
Reason: Skill folder names (e.g. "audit-orchestrator") contain hyphens and are not
valid Python package identifiers, so skills can't cleanly import each other as
packages. A shared, hyphen-free `common/` package lets every skill's scripts import
the same schema/utilities via a `sys.path` insert, avoiding duplicated logic.

Decision: Use Pydantic's `HttpUrl` type (via a small wrapper model) for URL
validation instead of hand-rolled regex.
Reason: More robust against edge cases, and Pydantic is already a required
dependency for the report schema.


Decision: Add a distinct `Observation` model in `common/schema.py`, separate from
`Finding`.
Reason: The project's core anti-false-positive principle requires separating raw
measured facts (observations) from judged problems (findings). Specialist skills
should only ever emit Observations; only the orchestrator's later reasoning stage
promotes an Observation into a Finding.

Decision: Parse `robots.txt` "Sitemap:" and "Disallow:" lines manually via simple
line parsing rather than relying on `urllib.robotparser`.
Reason: Standard library `robotparser` doesn't reliably expose declared sitemap
URLs across Python versions, and manual parsing is simple, transparent, and easy
to unit test.

Decision: Send a descriptive custom User-Agent (`BrandAIReadinessAuditor/0.1`) on
all outbound requests.
Reason: Matches the "safe by default" / respectful-crawling requirement - lets
webmasters identify the audit bot in their logs.



Decision: Use Playwright's synchronous API (`sync_playwright`) rather than the
async API for render_checks.py.
Reason: Each skill script currently runs standalone via a simple CLI; sync
Playwright keeps the script simple and matches the style of the other
deterministic check scripts. Can be revisited if the orchestrator later needs
to run render checks concurrently across many pages.

Decision: Measure raw-vs-rendered content gap using word-count delta + a
difflib similarity ratio, rather than deep DOM diffing or field-specific
extraction (e.g. searching for "price" patterns).
Reason: Keeps the check fully generic and pattern-based per Adobe's
generalization requirement — it works on any unseen website, not just ones
with a known layout. Field-specific extraction (e.g. detecting a price) would
be a hardcoded, site-specific rule and is explicitly the kind of thing the
brief says to avoid at this layer; that reasoning is deferred to Gemini once
real evidence is aggregated.

Decision: Cap text compared by difflib to the first 20,000 characters per page.
Reason: Keeps runtime bounded and predictable on very large pages, supporting
the 5-minute total audit runtime requirement.


Decision: Extract fetch_raw_html()/fetch_rendered_html() out of render_checks.py
into a new skills/crawl-render-audit/scripts/fetchers.py, shared by
render_checks.py and structured_data_checks.py.
Reason: Both scripts needed identical raw-HTTP and Playwright-rendering logic;
duplicating it would violate the project's "modular functions, small focused
modules" engineering principle. Kept local to this skill (not in common/)
since it's crawl-render-audit-specific fetch mechanics, not shared across
skills.

Decision: Use extruct's `uniform=True` output mode for structured data
extraction, and only check json-ld, microdata, and opengraph syntaxes (not
RDFa or microformat).
Reason: uniform=True gives a consistent, simpler item shape across syntaxes.
JSON-LD, microdata, and OpenGraph cover the vast majority of real-world
schema.org and social-metadata usage; RDFa/microformat are rare enough on
modern sites that including them would add complexity without much signal.

Decision: Do not treat "no structured data found" as a finding at this layer -
only report counts/types/presence as an Observation.
Reason: Matches the project's explicit guidance that "no JSON-LD = always bad"
is too simplistic; whether missing structured data matters depends on page
type, which is a judgment made later using aggregated evidence, not here.

Known limitation (not yet addressed): running render_checks.py and
structured_data_checks.py back-to-back on the same URL currently launches two
separate Playwright browser sessions. Acceptable for now since each script is
independently runnable/testable; the orchestrator will need to consolidate
this into one shared render pass to stay within the 5-minute runtime budget.