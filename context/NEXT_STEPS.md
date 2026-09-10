# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1-9. Foundation, all specialist skills' first checks, orchestrator wiring  <-- DONE (Steps 1-9)
10. Wire audit-orchestrator to call all specialist skills and aggregate
    Observations  <-- DONE (Step 10)
11. Integrate Gemini reasoning layer (modular llm/ package)  <-- DONE (Step 11)
12. Consolidate Playwright renders into one shared pass  <-- DONE (Step 12)
13. freshness-corroboration: entity identity signals  <-- DONE (Step 13)
14. engagement-audit: intent-to-landing alignment  <-- DONE (Step 14)
15. Add pytest test suite (pure/deterministic logic; network/browser/LLM
    paths remain manually tested)  <-- DONE (Step 15)
16. Cross-finding deduplication (beyond per-item validation already in
    reasoning.py) - revisit if repeat/overlapping findings actually appear
    during broader testing
17. Test on multiple real (unseen-style) websites (Apple, Nike, Samsung,
    Notion, HubSpot, MIT, Stanford, Marriott, Reuters, smaller sites per
    the brief's research methodology); refine both Gemini prompts (main
    reasoning + assumed-intent) based on real results; tune false
    positives further
18. Measure and optimize overall runtime to comfortably stay under 5 minutes
19. Write README.md and finalize marketplace.json
20. Package and zip final submission

This sequence may change as we learn things during development — update this file
whenever it does.