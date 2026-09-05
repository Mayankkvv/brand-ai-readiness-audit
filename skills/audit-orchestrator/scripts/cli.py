"""
Command-line entrypoint for the audit-orchestrator skill.

Validates the input URL, calls all three specialist skills via
skill_runner, sends the aggregated Observations to the Gemini reasoning
layer (reasoning.py) to produce real Findings, and prints the assembled
AuditReport as JSON.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.schema import AuditReport  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

from skill_runner import run_all_specialist_skills  # sibling module, same folder
from reasoning import generate_findings  # sibling module, same folder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("audit-orchestrator")


def run_audit(url: str) -> AuditReport:
    """Validate the URL, run all specialist skills, reason over the evidence, assemble the report."""
    normalized_url = validate_and_normalize_url(url)
    observations = run_all_specialist_skills(normalized_url)
    findings = generate_findings(normalized_url, observations)

    report = AuditReport(site=normalized_url, observations=observations, findings=findings)
    report.recompute_summary()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit-orchestrator",
        description="Audit a website for AI discoverability and engagement issues.",
    )
    parser.add_argument("url", help="Website URL to audit, e.g. https://example.com")
    args = parser.parse_args(argv)

    try:
        report = run_audit(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    logger.info(
        "Collected %d observations, produced %d findings.",
        len(report.observations),
        len(report.findings),
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())