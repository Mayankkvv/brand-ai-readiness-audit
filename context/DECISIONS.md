# DECISIONS

Decision: Use Python as the primary implementation language.
Reason: Required/recommended by Adobe brief; strong ecosystem for crawling, parsing,
and LLM orchestration.

Decision: Use Playwright for rendering rather than Selenium.
Reason: Faster, better modern API, reliable headless rendering for raw-vs-rendered
HTML comparison.

Decision: Use Google Gemini API as the initial LLM provider, behind a modular
llm/provider.py interface.
Reason: Free tier available for development; brief requires provider-neutrality, so
the interface must allow swapping providers later without rewriting audit logic.

Decision: Development happens on Windows; all commands given in PowerShell.
Reason: Matches the developer's actual environment.