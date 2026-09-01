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
> Status: placeholder — deterministic checks (robots.txt, sitemap, HTTP status,
> raw vs. rendered HTML via Playwright, structured data via extruct) will be
> implemented in a later step.

## Output
A list of evidence-backed observations about crawlability, rendering, and
structured data, to be consumed by audit-orchestrator.