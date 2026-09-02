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