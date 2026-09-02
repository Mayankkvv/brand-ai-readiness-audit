"""
URL validation and normalization shared across the marketplace's skills.
"""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl, ValidationError


class _UrlModel(BaseModel):
    url: HttpUrl


def validate_and_normalize_url(raw_url: str) -> str:
    """
    Validate that `raw_url` is a usable http(s) URL and return a normalized
    string form of it.

    - Strips surrounding whitespace.
    - Adds an "https://" scheme if none was supplied.
    - Raises ValueError with a clear message if the result is not a valid URL.
    """
    candidate = (raw_url or "").strip()
    if not candidate:
        raise ValueError("URL must not be empty.")

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    try:
        validated = _UrlModel(url=candidate)
    except ValidationError as exc:
        raise ValueError(f"'{raw_url}' is not a valid URL: {exc}") from exc

    return str(validated.url)