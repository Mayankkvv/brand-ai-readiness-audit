# ARCHITECTURE (as actually implemented)

Status: Not yet implemented beyond folder scaffolding.

Target high-level flow:

Website URL
-> audit-orchestrator
-> crawl-render-audit
-> freshness-corroboration
-> engagement-audit
-> combined evidence
-> Gemini reasoning
-> finding validation / deduplication
-> severity + priority
-> final JSON report

This file will be updated as each skill is actually built, with real module/function
names and data flow, replacing the conceptual diagram above.