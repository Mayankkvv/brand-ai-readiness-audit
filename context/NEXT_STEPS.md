# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1-14. Foundation through full skill implementation  <-- DONE (Steps 1-14)
15. Add pytest test suite  <-- DONE (Step 15)
16. Build a multi-site research testing harness; found and fixed a real
    raw_html/full_render_session coupling bug via testing (confirmed fixed
    on apple.com)  <-- DONE (Step 16), testing PARTIALLY complete
17. Write README.md and finalize marketplace.json  <-- DONE (Step 17,
    reordered ahead of full research-batch completion due to Gemini quota
    exhaustion)
18. RESUME the research batch once Gemini quota resets: run the remaining
    8 default sites (Nike, Samsung, Notion, HubSpot, MIT, Stanford,
    Marriott, Reuters), review results, refine prompts/checks based on
    real findings
19. Cross-finding deduplication - only if Step 18 actually surfaces
    repeat/overlapping findings
20. Measure and optimize overall runtime to comfortably stay under 5 minutes
21. Package the final submission ZIP - explicitly EXCLUDE tools/,
    research_output/, tests/, pytest.ini, .venv/, .env, context/, and
    other dev-only artifacts; verify size stays under 50MB

This sequence may change as we learn things during development — update this file
whenever it does.