# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1. Initialize repository and context system  <-- DONE (Step 1)
2. Create marketplace.json and skills/ folder skeleton  <-- DONE (Step 2)
3. Build shared schema + working orchestrator CLI  <-- DONE (Step 3)
4. crawl-render-audit: HTTP/robots.txt/sitemap checks  <-- DONE (Step 4)
5. crawl-render-audit: Playwright render diff  <-- DONE (Step 5)
6. crawl-render-audit: structured data checks (extruct)  <-- DONE (Step 6)
7. crawl-render-audit: hidden image-text detection (OCR)  <-- DONE (Step 7)
   crawl-render-audit is feature-complete and validated against real sites.
8. freshness-corroboration: date/freshness signal detection  <-- DONE (Step 8)
9. engagement-audit: first-screen, CTA, trust, readability checks  <-- DONE (Step 9)
10. Wire audit-orchestrator to call all specialist skills and aggregate
    Observations  <-- DONE (Step 10)
11. Integrate Gemini reasoning layer (modular llm/ package) to turn
    aggregated Observations into real Findings  <-- DONE (Step 11)
    AuditReport now populates findings + summary end-to-end.
12. freshness-corroboration: claim consistency, external corroboration,
    entity ambiguity (now that Gemini is wired, this can lean on it)
13. engagement-audit: intent-to-landing alignment + context retention (needs
    an "assumed user intent" input; can reuse the LLM layer)
14. Cross-finding deduplication (beyond the per-item validation already done
    in reasoning.py) - relevant once repeat/overlapping evidence appears
15. Add pytest test suite
16. Consolidate the multiple independent Playwright render passes (across
    crawl-render-audit and engagement-audit) into one shared render per
    audited page - dedicated runtime-optimization step
17. Test on multiple real (unseen-style) websites; refine the Gemini
    reasoning prompt based on real results; tune false positives
18. Optimize overall runtime to stay under 5 minutes
19. Write README.md and finalize marketplace.json
20. Package and zip final submission

This sequence may change as we learn things during development — update this file
whenever it does.