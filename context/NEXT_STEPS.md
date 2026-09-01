# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1. Initialize repository and context system  <-- DONE (Step 1)
2. Create marketplace.json and skills/ folder skeleton  <-- DONE (Step 2)
2. Create marketplace.json and skills/ folder skeleton
3. Create audit-orchestrator skill (SKILL.md + scripts scaffold)
4. Create crawl-render-audit skill (robots/sitemap/HTTP checks)
5. Add Playwright rendering + raw-vs-rendered HTML diff
6. Add structured data (JSON-LD/extruct) checks
7. Create freshness-corroboration skill
8. Create engagement-audit skill
9. Build evidence aggregation layer in orchestrator
10. Integrate Gemini reasoning layer (modular llm/ package)
11. Build Pydantic models + final report validation
12. Add finding deduplication / severity normalization
13. Add pytest test suite
14. Test on multiple real (unseen-style) websites, tune false positives
15. Optimize runtime to stay under 5 minutes
16. Write README.md and finalize marketplace.json
17. Package and zip final submission

This sequence may change as we learn things during development — update this file
whenever it does.