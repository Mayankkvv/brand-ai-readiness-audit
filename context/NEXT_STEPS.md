# NEXT STEPS (high-level plan — for orientation only, not a multi-step dump)

1-20. Foundation through full research-batch validation and packaging tool  <-- DONE (Steps 1-20)
21. Multi-page crawling, part 1: representative page discovery
    (about/pricing/products/services/contact/docs, keyword-based,
    robots.txt-aware)  <-- DONE (Step 21, discovery only)
22. Multi-page crawling, part 2: wire discovered pages into actual
    per-page auditing, with a runtime budget decision (e.g. full checks
    on homepage, lighter checks on secondary pages) - HIGH PRIORITY,
    explicit brief requirement (Section 22)
23. Proactive recommendations when nothing critical is found - HIGH
    PRIORITY, explicit brief requirement (Section 15), currently
    contradicted by the reasoning prompt
24. Cross-finding deduplication - named brief requirement (Section 6),
    currently deferred as not-yet-needed
25. Actually run tools/package_submission.py and verify the real ZIP
    (contents, size under 50MB)
26. End-to-end sanity check: unzip the package elsewhere, confirm cli.py
    runs correctly from the extracted copy alone
27. Optional polish: references/ folders (currently empty across all 4
    skills), robots.txt duplicate-path cosmetic fix

This sequence may change as we learn things during development — update this file
whenever it does.