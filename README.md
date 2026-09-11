# Brand AI Readiness Audit

An Agent Skill Marketplace that audits any website URL for problems affecting:

1. **AI discoverability** — why AI assistants and search systems might fail to
   find, understand, trust, or correctly cite the site or its information.
2. **On-site engagement** — why a visitor arriving on the site (e.g. sent there
   by an AI assistant) might fail to understand the page, retain context, or
   continue engaging.

This is not a generic SEO scanner, chatbot, or website analyzer. Every check
produces measured, reproducible **evidence** first; an LLM reasoning layer then
interprets that evidence to decide which observations represent genuine,
evidence-backed problems — never inventing a finding without supporting data.

## What the marketplace does

Given a URL, the marketplace:

1. Validates the URL.
2. Runs deterministic checks across three specialist skills (crawlability,
   rendering, structured data, freshness, entity identity, first-screen
   orientation, trust signals, and intent alignment).
3. Sends the collected evidence to an LLM (Gemini) in a small, bounded number
   of reasoning calls to produce specific, prioritized, evidence-backed
   findings.
4. Returns a single structured JSON report: site, timestamp, a severity
   summary, the findings, and the raw observations behind them.

## Skills

| Skill | Role |
|---|---|
| **audit-orchestrator** | **Entrypoint.** Validates the URL, calls the three specialist skills below, runs the LLM reasoning layer over their combined evidence, and assembles the final report. |
| **crawl-render-audit** | HTTP accessibility, `robots.txt`, sitemap discovery, raw-HTML-vs-rendered-DOM diffing, structured data (JSON-LD/microdata/OpenGraph), and hidden text-in-images detection (OCR). |
| **freshness-corroboration** | Date/freshness signals (meta tags, JSON-LD dates, visible "last updated" text, copyright years) and entity identity signals (JSON-LD Organization data, name self-descriptions, domain, address text). |
| **engagement-audit** | First-screen orientation, call-to-action/trust/navigation signal detection, content readability, and intent-to-landing-page alignment (comparing an independent LLM assumption of the site's purpose against its actual above-fold content). |

`audit-orchestrator` is the **only** skill marked as the entrypoint in
`marketplace.json`. It composes the other three by:

1. Running `crawl-render-audit`'s non-rendering checks (HTTP/robots/sitemap)
   independently.
2. Opening **one shared Playwright render** of the target page and passing it
   to every rendering-dependent check across all three specialist skills —
   avoiding redundant page loads and the runtime/reliability cost of each
   check rendering separately.
3. Sending every check's raw evidence (`Observation` objects) to the LLM
   reasoning layer in a single combined call to produce `Finding` objects.
4. Validating and assembling the final `AuditReport`.

## How to use it
python skills/audit-orchestrator/scripts/cli.py <url>


This prints the full JSON report to stdout. Each specialist script is also
independently runnable for testing/debugging, e.g.:

python skills/crawl-render-audit/scripts/access_checks.py <url>
python skills/engagement-audit/scripts/engagement_checks.py <url>


## Setup

1. **Python 3.10+** and a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Install the Playwright browser binary (one-time): `playwright install chromium`
4. Install the [Tesseract OCR engine](https://github.com/UB-Mannheim/tesseract/wiki)
   separately (not a pip package) for the hidden-image-text check. If it isn't
   on your system PATH, set the `TESSERACT_CMD` environment variable to its
   full path.
5. Copy `.env.example` to `.env` and add a Gemini API key from
   [Google AI Studio](https://aistudio.google.com/apikey). Without a key, the
   audit still runs and returns raw observations, but produces no findings.

## Report schema

```json
{
  "site": "example.com",
  "audited_at": "2026-...",
  "summary": {
    "total_findings": 2,
    "critical": 0, "high": 1, "medium": 1, "low": 0, "informational": 0
  },
  "findings": [
    {
      "id": "F-001",
      "title": "...",
      "severity": "high",
      "evidence": "...",
      "suggested_action": { "summary": "...", "priority": "high" },
      "category": "...",
      "confidence": 0.9
    }
  ],
  "observations": [ "...raw evidence from every specialist skill..." ]
}
```

`findings` are evidence-backed conclusions; `observations` are the raw,
deterministic measurements those conclusions were drawn from — included for
transparency into what the audit actually checked.

## Safety

This marketplace is **read-only and recommend-only**. It never modifies a
live website, performs no authenticated-area or destructive actions, respects
`robots.txt`, and uses bounded, rate-conscious crawling (a small number of
representative pages, a capped number of images per audit, a descriptive
User-Agent identifying the bot).

## Known limitations

- **External corroboration** (checking site claims against independent
  third-party sources via live web search) is explicitly out of scope — it
  would require per-claim search/LLM calls that conflict with the runtime
  and free-tier rate-limit constraints this project targets. Freshness and
  entity-identity checks rely on the site's own internal signals plus LLM
  reasoning, not external verification.
- LLM reasoning uses a small, bounded number of calls per audit (currently
  two: one independent "assumed intent" query, one main findings-reasoning
  call) rather than one call per check, per the project's efficiency goals.
- Model availability for the configured LLM provider (Gemini) changes over
  time; see `llm/gemini.py` if the configured model stops responding.