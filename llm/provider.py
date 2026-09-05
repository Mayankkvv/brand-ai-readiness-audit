"""
Modular LLM provider interface for audit-orchestrator's reasoning layer.

Keeps the audit logic decoupled from any specific LLM vendor, per the
project's requirement that the system "should NOT hardcode the entire
project around Gemini." The initial implementation (llm/gemini.py) uses
Google's Gemini API; a new provider can be added later by implementing
LLMProvider and registering it in get_provider() below, without touching
reasoning.py or any specialist skill.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()  # loads .env if present; a safe no-op if it doesn't exist


class ProviderConfigError(Exception):
    """Raised when the configured LLM provider is missing required setup (e.g. an API key)."""


class LLMProvider(ABC):
    """Abstract interface every LLM provider implementation must satisfy."""

    @abstractmethod
    def generate_json(self, system_instruction: str, user_prompt: str) -> str:
        """
        Send a prompt to the LLM and return its raw text response, expected
        to be a JSON document per `system_instruction`. Callers are
        responsible for parsing/validating the returned text - a provider
        should never be trusted to guarantee well-formed JSON on its own.
        """
        raise NotImplementedError


def get_provider() -> LLMProvider:
    """
    Return the configured LLM provider, based on the LLM_PROVIDER environment
    variable (default: "gemini"). Raises ProviderConfigError if required
    configuration (e.g. an API key) is missing, so callers can degrade
    gracefully instead of crashing the whole audit.
    """
    provider_name = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()

    if provider_name == "gemini":
        # Local import: avoids a hard dependency on google-genai for anyone
        # who configures a different provider in the future.
        from llm.gemini import GeminiProvider

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add "
                "your key, or set the environment variable directly."
            )
        #model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        return GeminiProvider(api_key=api_key, model_name=model_name)

    raise ProviderConfigError(f"Unknown LLM_PROVIDER: '{provider_name}'")