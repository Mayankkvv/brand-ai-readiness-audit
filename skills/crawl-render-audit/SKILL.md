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
5. *(not yet implemented)* Render the page with Playwright and diff raw HTML vs.
   the rendered DOM to detect JavaScript-dependent content.
6. *(not yet implemented)* Inspect structured data (JSON-LD via extruct) for
   presence, validity, and consistency with visible content.
7. *(not yet implemented)* Detect important facts exposed only via images/visual
   content with no equivalent readable text.
8. Return all findings as a list of `Observation` objects (`common/schema.py`) -
   raw measured facts, not yet judged as problems.

## Output
A list of `Observation` objects to be consumed by audit-orchestrator. Each
observation has `id`, `skill`, `category`, `description`, and a `data` dict with
the specific measured values (status codes, counts, URLs, etc.).

Run it standalone with:
```
python skills/crawl-render-audit/scripts/access_checks.py <url>
```