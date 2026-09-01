# PROJECT CONTEXT — Adobe University Hackathon 2026, Round 3

## Objective
Build a reusable "Agent Skill Marketplace" that takes any website URL and audits it
(read-only) for problems affecting:
1. AI Discoverability — why AI assistants/search systems may fail to find, understand,
   trust, or correctly cite the site.
2. On-site Engagement — why a visitor arriving on the site may fail to understand it,
   retain context, or continue engaging.

This is NOT a generic SEO tool, chatbot, or website analyzer. It must encode
*generalizable, evidence-based reasoning* that works on websites never seen before.

## Non-negotiable Adobe requirements
- Submission = single marketplace package: `marketplace.json`, `README.md`,
  `skills/` (each with a valid `SKILL.md`), exactly ONE skill marked `"entrypoint": true`.
- Final ZIP of the marketplace root, max 50MB, no pretrained model weights included.
- Provider-neutral, self-contained.
- Typical audit completes in under 5 minutes on a standard machine.
- Read-only / recommend-only: never modifies a live site, no destructive or
  authenticated-area actions, no rate-abusing crawling, must respect `robots.txt`.

## Planned architecture
Website URL
-> audit-orchestrator (SOLE ENTRYPOINT)
-> crawl-render-audit (crawlability, rendering, structured data, non-text facts)
-> freshness-corroboration (stale/conflicting facts, entity ambiguity, corroboration)
-> engagement-audit (first-screen orientation, intent alignment, nav, trust)
-> combined evidence
-> Gemini reasoning (interprets evidence, never invents it)
-> finding validation / deduplication
-> severity + priority
-> final structured JSON report


## Report schema (minimum required fields)
```json
{
  "site": "example.com",
  "audited_at": "...",
  "summary": { "total_findings": 0, "critical": 0, "high": 0, "medium": 0 },
  "findings": [
    {
      "id": "F-001",
      "title": "...",
      "severity": "high",
      "evidence": "...",
      "suggested_action": { "summary": "...", "priority": "high" }
    }
  ]
}
```
Optional extra fields allowed: category, confidence, affected_pages, impact,
implementation_notes, verification_method.

## Tech stack
- Python (main language)
- httpx (HTTP)
- Playwright (browser rendering)
- BeautifulSoup (HTML parsing)
- Trafilatura (main content extraction)
- extruct (structured data / JSON-LD)
- Pydantic (data validation)
- Google Gemini API as the initial LLM, behind a modular `llm/provider.py` interface
  so it can be swapped later — never hardcode logic around Gemini specifically.
- pytest (testing)
- Dev machine: Windows, PowerShell

## LLM architecture rule
Never send just a URL to Gemini and ask it to "audit this." Deterministic Python code
must collect evidence first (HTML, rendered DOM, robots.txt, sitemap, structured data,
dates, etc.). Gemini only reasons over that evidence — it never invents facts. Keep
Gemini calls few and batched (free-tier rate limits + 5-minute runtime budget).

## Severity model
critical > high > medium > low > (optional) informational.
Fewer, stronger, evidence-backed findings are preferred over many generic ones.
Every finding needs: id, title, severity, evidence, suggested_action {summary, priority}.

## Things we are explicitly NOT building
SEO dashboard, generic chatbot, website builder/editor, CMS, login system, SaaS
platform, unnecessary MERN app, a crawler that downloads the whole site, an LLM that
makes unsupported claims, anything that modifies websites.

## Working mode for this project
Strictly one implementation step at a time. Every step: short explanation, exact
files/commands, complete code (no snippets/TODOs), exact paste locations, test
instructions, then git status/add/commit/push. Wait for explicit "next step" before
continuing. Windows PowerShell commands only.