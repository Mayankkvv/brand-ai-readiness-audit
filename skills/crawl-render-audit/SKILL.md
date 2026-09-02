---
name: crawl-render-audit
description: Checks crawlability, robots.txt, sitemap, raw-HTML-vs-rendered-DOM differences, structured data (JSON-LD), and non-text/hidden facts on a target website, producing evidence for the orchestrator.
license: MIT
---

# Crawl & Render Audit

## When to use
Called by audit-orchestrator to assess technical discoverability and machine
extractability of a website's content.

## Inputs
- `url` (string, required): the website to audit.

## Procedure
1. Validate and normalize the URL (`common/url_utils.py`).
2. Check HTTP accessibility of the homepage: status code and redirect chain
   (`scripts/access_checks.py::check_http_status`). **[DONE]**
3. Fetch and parse `robots.txt`: existence, disallowed paths, declared sitemaps
   (`scripts/access_checks.py::fetch_robots_txt`). **[DONE]**
4. Discover and parse a sitemap, preferring robots.txt-declared sitemaps and
   falling back to `/sitemap.xml`; report URL count and sample URLs
   (`scripts/access_checks.py::discover_sitemap`). **[DONE]**
5. Render the homepage with Playwright and compare its visible text against the
   plain-HTTP-fetched HTML: word count delta, percentage increase, and text
   similarity ratio (`scripts/render_checks.py::run_render_checks`). **[DONE]**
   This is a measurement only — a content gap here is not automatically a
   problem; whether it matters is decided later using the actual affected
   content, not just the presence of a gap.
6. *(not yet implemented)* Inspect structured data (JSON-LD via extruct) for
   presence, validity, and consistency with visible content.
7. *(not yet implemented)* Detect important facts exposed only via images/visual
   content with no equivalent readable text.
8. Return all findings as a list of `Observation` objects (`common/schema.py`) -
   raw measured facts, not yet judged as problems.

## Output
A list of `Observation` objects to be consumed by audit-orchestrator. Each
observation has `id`, `skill`, `category`, `description`, and a `data` dict with
the specific measured values (status codes, counts, URLs, word counts, etc.).

Run the checks standalone with:
```
python skills/crawl-render-audit/scripts/access_checks.py <url>
python skills/crawl-render-audit/scripts/render_checks.py <url>
```