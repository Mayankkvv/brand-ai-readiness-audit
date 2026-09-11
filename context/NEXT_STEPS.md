# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1-9. Foundation, all specialist skills' first checks, orchestrator wiring  <-- DONE (Steps 1-9)
10. Wire audit-orchestrator to call all specialist skills and aggregate
    Observations  <-- DONE (Step 10)
11. Integrate Gemini reasoning layer (modular llm/ package)  <-- DONE (Step 11)
12. Consolidate Playwright renders into one shared pass  <-- DONE (Step 12)
13. freshness-corroboration: entity identity signals  <-- DONE (Step 13)
14. engagement-audit: intent-to-landing alignment  <-- DONE (Step 14)
15. Add pytest test suite  <-- DONE (Step 15)
16. Build a multi-site research testing harness  <-- DONE (Step 16)
17. RUN the research batch, review results, refine both Gemini prompts and
    any checks based on real findings/false positives it surfaces - the
    actual research step, now that the tooling exists
18. Cross-finding deduplication - revisit only if repeat/overlapping
    findings actually appear during Step 17's real testing
19. Measure and optimize overall runtime to comfortably stay under 5 minutes
20. Write README.md and finalize marketplace.json
21. Package the final submission ZIP - explicitly EXCLUDE tools/,
    research_output/, .venv/, .env, and other dev-only artifacts

This sequence may change as we learn things during development — update this file
whenever it does.