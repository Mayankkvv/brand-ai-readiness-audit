from common.schema import AuditReport, Finding, Priority, Severity, SuggestedAction


def _make_finding(severity: Severity) -> Finding:
    return Finding(
        id="F-001",
        title="Test finding",
        severity=severity,
        evidence="Some evidence",
        suggested_action=SuggestedAction(summary="Fix it", priority=Priority.MEDIUM),
    )


def test_recompute_summary_counts_by_severity():
    report = AuditReport(site="https://example.com/")
    report.findings = [
        _make_finding(Severity.HIGH),
        _make_finding(Severity.HIGH),
        _make_finding(Severity.LOW),
    ]
    report.recompute_summary()

    assert report.summary.total_findings == 3
    assert report.summary.high == 2
    assert report.summary.low == 1
    assert report.summary.critical == 0
    assert report.summary.medium == 0
    assert report.summary.informational == 0


def test_recompute_summary_with_no_findings():
    report = AuditReport(site="https://example.com/")
    report.recompute_summary()

    assert report.summary.total_findings == 0
    assert report.summary.critical == 0