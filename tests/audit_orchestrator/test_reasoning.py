import json

import pytest

from reasoning import _normalize_enum_casing, _parse_findings


def test_parse_findings_valid_json_array():
    raw = json.dumps(
        [
            {
                "title": "Missing sitemap",
                "severity": "medium",
                "evidence": "No sitemap.xml found and none declared in robots.txt.",
                "suggested_action": {"summary": "Add a sitemap.", "priority": "medium"},
            }
        ]
    )
    findings = _parse_findings(raw)

    assert len(findings) == 1
    assert findings[0].id == "F-001"
    assert findings[0].title == "Missing sitemap"


def test_parse_findings_strips_markdown_code_fences():
    raw = "```json\n[]\n```"
    findings = _parse_findings(raw)
    assert findings == []


def test_parse_findings_skips_invalid_items_but_keeps_valid_ones():
    raw = json.dumps(
        [
            {
                "title": "Valid one",
                "severity": "low",
                "evidence": "some evidence",
                "suggested_action": {"summary": "fix", "priority": "low"},
            },
            {
                "title": "Missing evidence field",
                "severity": "low",
                "suggested_action": {"summary": "fix", "priority": "low"},
            },
        ]
    )
    findings = _parse_findings(raw)

    assert len(findings) == 1
    assert findings[0].title == "Valid one"


def test_parse_findings_rejects_non_list_json():
    raw = json.dumps({"not": "a list"})
    with pytest.raises(ValueError):
        _parse_findings(raw)


def test_normalize_enum_casing_lowercases_severity_and_priority():
    item = {"severity": "HIGH", "suggested_action": {"priority": "MEDIUM"}}
    normalized = _normalize_enum_casing(item)

    assert normalized["severity"] == "high"
    assert normalized["suggested_action"]["priority"] == "medium"