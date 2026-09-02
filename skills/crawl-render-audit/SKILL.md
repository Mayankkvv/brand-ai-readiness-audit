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
6. Inspect structured data (JSON-LD, microdata, OpenGraph via `extruct`) in both
   raw and rendered HTML: presence, declared schema.org types, and whether
   JSON-LD only appears after rendering (`scripts/structured_data_checks.py`).
   **[DONE]**
7. Scan a bounded set of content-sized images (skipping icons/logos/tracking
   pixels) with OCR (Tesseract via `pytesseract`), and measure how much of the
   extracted text already appears in the page's visible text
   (`scripts/image_checks.py::run_image_text_checks`). **[DONE]** A low overlap
   ratio is a measured gap, not automatically a finding — whether the missing
   text represents an important claim is judged later.
8. Return all findings as a list of `Observation` objects (`common/schema.py`) -
   raw measured facts, not yet judged as problems.

**crawl-render-audit's planned checks are now complete.** Remaining work for this
skill is wiring it into audit-orchestrator (Step 10+).

## Output
A list of `Observation` objects to be consumed by audit-orchestrator. Each
observation has `id`, `skill`, `category`, `description`, and a `data` dict with
the specific measured values (status codes, counts, URLs, word counts,
structured-data types, OCR text samples, etc.).

Run the checks standalone with:
```
python skills/crawl-render-audit/scripts/access_checks.py <url>
python skills/crawl-render-audit/scripts/render_checks.py <url>
python skills/crawl-render-audit/scripts/structured_data_checks.py <url>
python skills/crawl-render-audit/scripts/image_checks.py <url>
```