"""
Shared pytest setup: adds the project root and every skill's scripts/
directory to sys.path, so tests can import modules the same way
audit-orchestrator's skill_runner.py does (and the same way each script
imports its own sibling modules when run standalone) - e.g.
`from render_checks import extract_visible_text` without needing skill
folders to be proper Python packages (their hyphenated names aren't valid
package names anyway).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SKILL_SCRIPT_DIRS = [
    PROJECT_ROOT / "skills" / "crawl-render-audit" / "scripts",
    PROJECT_ROOT / "skills" / "freshness-corroboration" / "scripts",
    PROJECT_ROOT / "skills" / "engagement-audit" / "scripts",
    PROJECT_ROOT / "skills" / "audit-orchestrator" / "scripts",
]
for _dir in SKILL_SCRIPT_DIRS:
    sys.path.insert(0, str(_dir))