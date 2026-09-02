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


Decision: Use OCR (Tesseract via pytesseract) rather than Gemini Vision to detect
text embedded in images.
Reason: Keeps this check deterministic and reproducible, consistent with the
"deterministic before LLM" principle - the same image always produces the same
extracted text. It also avoids spending scarce Gemini free-tier calls on a raw
extraction task; Gemini's reasoning is reserved for judging whether an
extracted claim actually matters, which happens later.

Decision: Filter candidate images by filename hints (icon/logo/sprite/favicon/
avatar) and minimum dimensions (200x120), and cap scanning to the 8 largest
images per page.
Reason: Avoids wasting OCR time on decorative UI chrome, keeps the check
generic (no site-specific rules), and bounds runtime per the 5-minute total
audit budget.

Decision: Measure "text only in image" via word-overlap ratio (OCR words also
found in page visible text) rather than exact substring matching.
Reason: OCR output often has minor spacing/casing/line-break differences from
how the same text might be phrased elsewhere on the page; word-set overlap is
more robust to that noise while still being simple and explainable.

Known limitation (not yet addressed): crawl-render-audit's three
rendering-dependent scripts (render_checks, structured_data_checks,
image_checks) each currently launch a separate Playwright session against the
same URL. This will be consolidated into a single shared render pass when the
orchestrator wires these scripts together, both for runtime efficiency and to
guarantee all three see the identical rendered snapshot.



Decision: Move fetch_raw_html()/fetch_rendered_html() from
skills/crawl-render-audit/scripts/fetchers.py into common/fetch_utils.py.
Reason: freshness-corroboration's date_signals.py needs the identical
rendered-HTML fetch logic. What was a crawl-render-audit-specific helper in
Step 6 turned out to be genuinely cross-skill, so it moved into the shared
common/ package rather than being duplicated a second time.

Decision: Use simple regex patterns for visible "last updated"/"published on"
text and copyright-year notices, rather than a full date-parsing library (e.g.
dateutil) at this stage.
Reason: Keeps the check dependency-light and generic across unseen websites;
exact date parsing/normalization can be added later if the orchestrator's
reasoning stage needs machine-comparable dates rather than raw text evidence.

Decision: Do not compute or report an "is_stale" verdict in date_signals.py -
only raw signals (dates found, copyright-year gap as a number).
Reason: Matches the project's explicit rule that absence of a date is evidence
of lower transparency, not proof of staleness - that judgment requires context
(page type, industry norms) that belongs in the later reasoning stage, not in
a deterministic check.


Decision: Add rendered_page_session() to common/fetch_utils.py, yielding a
live Playwright Page rather than just an HTML string.
Reason: Determining what's actually visible "above the fold" requires real
rendered layout information (getBoundingClientRect()), which only exists
while the page is live in the browser - a static HTML string can't answer
that question, since layout depends on CSS/JS execution, not source order.

Decision: Detect calls-to-action via a fixed list of generic English action
verbs/phrases (e.g. "sign up", "get started", "buy") rather than any
site-specific button styling or ML classification.
Reason: Keeps the check fully generalizable to unseen websites per Adobe's
requirement - a hardcoded selector or learned classifier tuned to known
sites would be exactly the kind of overfitting the brief warns against.
Acknowledged limitation: this will miss non-English CTAs and icon-only
buttons with no text; refining the keyword list based on real testing is
tracked in NEXT_STEPS/TESTING, not solved definitively in this step.

Decision: Use textstat's Flesch reading-ease score as the content-clarity
proxy, skipping the calculation entirely when visible text is under 30 words.
Reason: A well-established, deterministic, library-based readability metric
avoids inventing a custom heuristic. The word-count floor avoids a
meaningless score on pages that are mostly navigation/images with little
prose (the algorithm becomes unreliable on very short text).

Decision: Explicitly defer intent-to-landing alignment and context retention
rather than approximating them without a real "assumed user intent" input.
Reason: Both checks are meaningless without knowing what an AI assistant
told the visitor beforehand. Guessing at a plausible intent from the page's
own content would be circular (the page could never "misalign" with a guess
derived from itself) and would produce fake-looking findings with no real
evidence behind them - directly against the project's evidence-first
principle.


Decision: Load each specialist skill's script modules via
`importlib.util.spec_from_file_location()` inside a new skill_runner.py,
rather than restructuring skill folders into importable Python packages.
Reason: Skill folder names (e.g. "audit-orchestrator", "crawl-render-audit")
are required by the Adobe Agent Skills format and contain hyphens, which are
invalid in Python package/module names. Dynamic file-path loading lets each
skill's scripts stay runnable both standalone (as already tested in Steps
4-9) and from the orchestrator, without renaming any skill folder.

Decision: Wrap each specialist check individually in skill_runner.py so one
failing check becomes an error Observation rather than raising and aborting
the whole audit.
Reason: Directly required by the brief's failure-handling section - "one
failed page must not crash the entire audit" and "clearly distinguish 'not
checked' from 'checked and no issue found'." An error Observation makes a
failed check visible and inspectable rather than silently dropped or fatal.

Decision: Add an `observations` field directly to `AuditReport` rather than
keeping raw evidence in a separate, unlogged data structure.
Reason: The brief explicitly encourages "additional fields... when useful"
in the final report, and surfacing raw evidence supports transparency and
easier debugging while the reasoning layer doesn't exist yet. This field may
be trimmed or renamed once Gemini reasoning is built and evidence is
consumed rather than displayed directly - noted in DEVELOPMENT_STATE.md.

Decision: Defer consolidating crawl-render-audit's and engagement-audit's
multiple independent Playwright render passes into one shared pass, rather
than doing it as part of this step.
Reason: Wiring the orchestrator (calling all skills, aggregating evidence,
fault isolation) is already a meaningful, testable unit of work on its own.
Combining it with a nontrivial rendering-architecture change would violate
the "one step at a time" / "build one capability at a time" development
rule. Performance optimization is explicitly listed as a dedicated later
step in NEXT_STEPS.md.