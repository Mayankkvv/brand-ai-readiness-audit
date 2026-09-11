"""
Multi-site research/testing harness - NOT part of the marketplace
submission (lives outside skills/, will be excluded from the final zip).

Runs audit-orchestrator against a curated list of real websites, per the
Adobe brief's research methodology: identify repeatable, general patterns
by testing against real, varied sites - NEVER hardcode site-specific
behavior into the checks themselves. This script exists only to make that
research faster to run and review; it must not influence the marketplace's
actual detection logic beyond what real findings teach us.

Saves each full report to research_output/<domain>.json (gitignored - working
notes, not submission material) and prints a summary table. One site
failing entirely does not stop the batch.

Usage:
    python tools/run_research_batch.py
    python tools/run_research_batch.py --sites https://example.com https://another.com
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_SCRIPTS = PROJECT_ROOT / "skills" / "audit-orchestrator" / "scripts"
OUTPUT_DIR = PROJECT_ROOT / "research_output"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ORCHESTRATOR_SCRIPTS))

from cli import run_audit  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("research_batch")

# Research sites per the Adobe brief's suggested research methodology.
# Used ONLY to discover general, repeatable patterns and sanity-check the
# auditor against real, varied sites - never to hardcode site-specific
# logic. The final marketplace must generalize to sites NOT on this list.
DEFAULT_RESEARCH_SITES = [
    "https://www.apple.com",
    "https://www.nike.com",
    "https://www.samsung.com",
    "https://www.notion.so",
    "https://www.hubspot.com",
    "https://www.mit.edu",
    "https://www.stanford.edu",
    "https://www.marriott.com",
    "https://www.reuters.com",
]


def _domain_slug(url: str) -> str:
    netloc = urlparse(url).netloc.removeprefix("www.")
    return netloc.replace(".", "_")


def run_batch(sites: List[str]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    rows = []

    for url in sites:
        print(f"Auditing {url} ...")
        start = time.monotonic()
        try:
            report = run_audit(url)
            elapsed = round(time.monotonic() - start, 1)
            failed_observations = [
                o for o in report.observations if o.data.get("checked") is False
            ]

            output_path = OUTPUT_DIR / f"{_domain_slug(url)}.json"
            output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            rows.append(
                {
                    "site": url,
                    "elapsed_seconds": elapsed,
                    "observations": len(report.observations),
                    "failed_observations": len(failed_observations),
                    "findings": len(report.findings),
                    "critical": report.summary.critical,
                    "high": report.summary.high,
                    "medium": report.summary.medium,
                    "low": report.summary.low,
                    "status": "ok",
                }
            )
        except Exception as exc:  # noqa: BLE001 - one bad site must not stop the batch
            elapsed = round(time.monotonic() - start, 1)
            logger.warning("Audit failed entirely for %s: %s", url, exc)
            rows.append(
                {
                    "site": url,
                    "elapsed_seconds": elapsed,
                    "observations": 0,
                    "failed_observations": 0,
                    "findings": 0,
                    "critical": 0, "high": 0, "medium": 0, "low": 0,
                    "status": f"FAILED: {exc}",
                }
            )

    print("\n" + "=" * 105)
    header = (
        f"{'Site':<32}{'Time':>7}{'Obs':>6}{'ObsFail':>9}{'Find':>6}"
        f"{'Crit':>6}{'High':>6}{'Med':>6}{'Low':>6}  Status"
    )
    print(header)
    print("-" * 105)
    for row in rows:
        print(
            f"{row['site']:<32}{row['elapsed_seconds']:>7}{row['observations']:>6}"
            f"{row['failed_observations']:>9}{row['findings']:>6}{row['critical']:>6}"
            f"{row['high']:>6}{row['medium']:>6}{row['low']:>6}  {row['status']}"
        )
    print("=" * 105)
    print(f"Full reports saved to: {OUTPUT_DIR}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run audit-orchestrator against a batch of research websites."
    )
    parser.add_argument(
        "--sites", nargs="+", default=None,
        help="Override the default research site list with your own URLs.",
    )
    args = parser.parse_args(argv)
    sites = args.sites if args.sites else DEFAULT_RESEARCH_SITES
    run_batch(sites)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())