# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1-20. Foundation through full research-batch validation and packaging tool  <-- DONE (Steps 1-20)
21. Multi-page crawling, part 1: representative page discovery  <-- DONE (Step 21)
22. Multi-page crawling, part 2: wire discovered pages into real
    per-page auditing (render diff + structured data, 2-page cap, zero
    extra Gemini calls)  <-- DONE (Step 22)
23. TEST Step 22 against a real site with clear pricing/product pages -
    verify secondary-page observations appear and findings correctly
    populate affected_pages
24. Proactive recommendations when nothing critical is found - HIGH
    PRIORITY, explicit brief requirement (Section 15), still unmet
25. Cross-finding deduplication - named brief requirement (Section 6),
    currently deferred as not-yet-needed
26. Re-run tools/package_submission.py (files changed since Step 20) and
    verify the real ZIP (contents, size under 50MB)
27. End-to-end sanity check: unzip the package elsewhere, confirm cli.py
    runs correctly from the extracted copy alone
28. Optional polish: references/ folders (empty across all 4 skills),
    robots.txt duplicate-path cosmetic fix

This sequence may change as we learn things during development — update this file
whenever it does.