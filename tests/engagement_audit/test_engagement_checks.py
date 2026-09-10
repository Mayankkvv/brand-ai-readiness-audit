"""
Includes explicit regression tests for the three real-world phone-number
false positives found during Steps 11-12 testing (a floating-point number,
a date stamp, and a Fibonacci-sequence code sample from python.org's
homepage) - the exact reason phone detection was rebuilt on the
`phonenumbers` library instead of a hand-rolled regex.
"""

from bs4 import BeautifulSoup

from engagement_checks import (
    _compute_readability,
    _extract_page_metadata,
    _find_cta_elements,
    _find_phone_numbers,
)


def test_extract_page_metadata():
    html = (
        "<html><head><title>My Site</title>"
        '<meta name="description" content="A great site.">'
        "</head><body><h1>Welcome</h1></body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    metadata = _extract_page_metadata(soup)

    assert metadata["title"] == "My Site"
    assert metadata["meta_description"] == "A great site."
    assert metadata["first_h1"] == "Welcome"


def test_find_cta_elements_matches_known_keywords():
    html = (
        "<a href='/signup'>Sign Up</a>"
        "<a href='/about'>About us</a>"
        "<button>Get Started</button>"
    )
    soup = BeautifulSoup(html, "html.parser")
    matches = _find_cta_elements(soup)

    assert "Sign Up" in matches
    assert "Get Started" in matches
    assert "About us" not in matches


def test_phone_detection_does_not_match_floating_point_number():
    text = "The result of floor division: 5.666666666666667 is shown here."
    assert _find_phone_numbers(text) == []


def test_phone_detection_does_not_match_date_stamp():
    text = "Last built on 2026- 09-01 using the latest tools."
    assert _find_phone_numbers(text) == []


def test_phone_detection_does_not_match_number_sequence():
    text = "Fibonacci: 1000 ) 0 1 1 2 3 5 8 13 21 34 55 89 144 233 377 610 987"
    assert _find_phone_numbers(text) == []


def test_phone_detection_matches_real_looking_number():
    # (202) is a real NANP area code; 555-01xx is the standard reserved
    # "fictional number" block for the exchange position - structurally
    # valid, unlike 555 in the area-code position (which isn't a real
    # area code at all, hence this note).
    text = "Call us at (202) 555-0123 for support."
    matches = _find_phone_numbers(text)
    assert len(matches) == 1


def test_compute_readability_skips_short_text():
    result = _compute_readability("Too short.")
    assert result["checked"] is False
    assert result["flesch_reading_ease"] is None


def test_compute_readability_scores_longer_text():
    text = " ".join(["This is a simple sentence for testing readability."] * 10)
    result = _compute_readability(text)
    assert result["checked"] is True
    assert isinstance(result["flesch_reading_ease"], float)