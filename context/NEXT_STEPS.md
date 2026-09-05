# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1-9. Foundation, all specialist skills' first checks, orchestrator wiring  <-- DONE (Steps 1-9)
10. Wire audit-orchestrator to call all specialist skills and aggregate
    Observations  <-- DONE (Step 10)
11. Integrate Gemini reasoning layer (modular llm/ package)  <-- DONE (Step 11)
    Includes fixes found via real testing: correct google-genai package,
    current model name, API key ambiguity fix, retry-on-transient-error,
    and a phone-number detection rebuild (phonenumbers library) after
    three rounds of regex false positives.
12. Consolidate the multiple independent Playwright render passes into one
    shared render per audited page  <-- DONE (Step 12)
13. freshness-corroboration: claim consistency, external corroboration,
    entity ambiguity (can lean on the now-working LLM layer)
14. engagement-audit: intent-to-landing alignment + context retention
    (needs an "assumed user intent" input; can reuse the LLM layer)
15. Cross-finding deduplication (beyond per-item validation already in
    reasoning.py)
16. Add pytest test suite
17. Test on multiple real (unseen-style) websites; refine the Gemini
    reasoning prompt based on real results; tune false positives further
18. Measure and optimize overall runtime to comfortably stay under 5 minutes
19. Write README.md and finalize marketplace.json
20. Package and zip final submission

This sequence may change as we learn things during development — update this file
whenever it does.