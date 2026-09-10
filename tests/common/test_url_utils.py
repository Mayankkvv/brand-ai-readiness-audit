import pytest

from common.url_utils import validate_and_normalize_url


def test_adds_https_scheme_when_missing():
    assert validate_and_normalize_url("example.com") == "https://example.com/"


def test_keeps_https_scheme_when_present():
    assert validate_and_normalize_url("https://example.com") == "https://example.com/"


def test_strips_surrounding_whitespace():
    assert validate_and_normalize_url("  example.com  ") == "https://example.com/"


def test_rejects_empty_string():
    with pytest.raises(ValueError):
        validate_and_normalize_url("")


def test_rejects_whitespace_only_string():
    with pytest.raises(ValueError):
        validate_and_normalize_url("   ")


def test_rejects_malformed_url():
    with pytest.raises(ValueError):
        validate_and_normalize_url("not a url")