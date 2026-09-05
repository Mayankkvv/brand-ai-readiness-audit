"""
Gemini implementation of the LLMProvider interface (see llm/provider.py).

Uses Google's current official `google-genai` SDK - NOT the older
`google-generativeai` package, which is now deprecated and no longer
supports current Gemini models.

Model availability changes fairly often. If GEMINI_MODEL (set via .env or
as an environment variable - see llm/provider.py) stops working, check
https://ai.google.dev/gemini-api/docs/models for the current list of
available model names and update .env. No code change should be needed.

Explicitly sets GOOGLE_API_KEY in the environment to match the key we were
given (see __init__). Found via testing: the google-genai SDK checks for
BOTH GOOGLE_API_KEY and GEMINI_API_KEY env vars and prefers GOOGLE_API_KEY
if both are present - regardless of what's passed explicitly to
genai.Client(api_key=...). Overwriting it here guarantees the key we were
actually given is the one used.

Retries transient server-side errors (e.g. 503 "high demand", 429 rate
limiting) with a short exponential backoff before giving up. Found via
testing: Gemini can return 503 UNAVAILABLE during demand spikes, and
Google's own error message says these are "usually temporary." Non-
transient errors (bad API key, unknown model, etc.) are raised immediately
without retrying.
"""

from __future__ import annotations

import logging
import os
import time

from google import genai
from google.genai import types

from llm.provider import LLMProvider

logger = logging.getLogger("llm.gemini")

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [2, 4, 8]
RETRYABLE_ERROR_HINTS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str) -> None:
        os.environ["GOOGLE_API_KEY"] = api_key
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    def generate_json(self, system_instruction: str, user_prompt: str) -> str:
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                if not response.text:
                    raise ValueError("Gemini returned an empty response.")
                return response.text
            except Exception as exc:  # noqa: BLE001 - inspected below, re-raised if not transient
                last_exc = exc
                message = str(exc)
                is_retryable = any(hint in message for hint in RETRYABLE_ERROR_HINTS)
                if not is_retryable or attempt == MAX_RETRIES:
                    raise
                wait_seconds = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "Gemini call failed (attempt %d/%d): %s - retrying in %ds",
                    attempt + 1, MAX_RETRIES + 1, message, wait_seconds,
                )
                time.sleep(wait_seconds)

        assert last_exc is not None  # unreachable, but satisfies type checkers
        raise last_exc