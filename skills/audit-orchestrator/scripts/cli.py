"""
Command-line entrypoint for the audit-orchestrator skill.

Current capability (Step 3): accepts a website URL, validates/normalizes it,
and emits a well-formed (but empty) AuditReport as JSON. This proves the
shared schema and CLI wiring work end-to-end before any real crawling or
Gemini reasoning is added in later steps.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Skill folder names contain hyphens (e.g. "audit-orchestrator"), which are
# not valid Python package names, so this script is run standalone rather
# than imported as part of a package. We add the project root to sys.path
# so the shared `common` package can be imported regardless of the
# directory this script is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from common.schema import AuditReport  # noqa: E402
from common.url_utils import validate_and_normalize_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("audit-orchestrator")


def build_placeholder_report(url: str) -> AuditReport:
    """Build an empty-findings report for a validated URL."""
    report = AuditReport(site=url)
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
        normalized_url = validate_and_normalize_url(args.url)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    logger.info("Validated URL: %s", normalized_url)
    logger.info(
        "Specialist skills (crawl-render-audit, freshness-corroboration, "
        "engagement-audit) are not implemented yet - emitting an empty report."
    )

    report = build_placeholder_report(normalized_url)
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())