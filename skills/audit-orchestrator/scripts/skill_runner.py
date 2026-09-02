"""
Skill runner for audit-orchestrator.

Dynamically imports each specialist skill's check functions - skill folder
names contain hyphens, so they can't be imported as normal Python packages -
and runs them all against a single validated URL, returning every skill's
Observations as one combined list.

Step 10 scope: call all three specialist skills and aggregate their raw
Observations. Turning these into real Findings (via Gemini reasoning,
deduplication, severity/priority assignment) is deferred to a later step.

One failing check must never crash the whole audit (per the brief's failure-
handling requirement): each check is wrapped individually, and a failure is
recorded as an error Observation rather than propagated.

Known limitation (tracked in context/DEVELOPMENT_STATE.md): each imported
check function currently opens its own independent Playwright browser
session, so a single orchestrator run currently renders the target page
multiple times (once each for render_checks, structured_data_checks,
image_checks, and engagement_checks). This will be consolidated into a
single shared render pass in a dedicated runtime-optimization step - see
context/NEXT_STEPS.md.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = PROJECT_ROOT / "skills"

sys.path.insert(0, str(PROJECT_ROOT))
from common.schema import Observation  # noqa: E402

logger = logging.getLogger("audit-orchestrator.skill_runner")

# (skill_name, scripts_dir, module_name, function_name, returns_list_of_observations)
# Order matters: render_checks must load before image_checks, since
# image_checks.py does `from render_checks import extract_visible_text` as a
# sibling import that relies on render_checks already being importable.
CHECKS = [
    ("crawl-render-audit", "crawl-render-audit", "access_checks", "run_access_checks", True),
    ("crawl-render-audit", "crawl-render-audit", "render_checks", "run_render_checks", False),
    ("crawl-render-audit", "crawl-render-audit", "structured_data_checks", "run_structured_data_checks", False),
    ("crawl-render-audit", "crawl-render-audit", "image_checks", "run_image_text_checks", False),
    ("freshness-corroboration", "freshness-corroboration", "date_signals", "run_date_signal_checks", False),
    ("engagement-audit", "engagement-audit", "engagement_checks", "run_engagement_checks", True),
]


def _load_module(module_name: str, scripts_dir: Path) -> types.ModuleType:
    """
    Import a skill script module by file path, adding its scripts/ directory
    to sys.path first so any sibling imports inside that module (e.g.
    image_checks.py importing render_checks.py) resolve correctly, exactly
    as they do when that script is run standalone.
    """
    scripts_dir_str = str(scripts_dir)
    if scripts_dir_str not in sys.path:
        sys.path.insert(0, scripts_dir_str)

    module_path = scripts_dir / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_all_specialist_skills(url: str) -> List[Observation]:
    """Run every implemented check across all three specialist skills."""
    observations: List[Observation] = []

    for skill_name, skill_folder, module_name, func_name, returns_list in CHECKS:
        scripts_dir = SKILLS_ROOT / skill_folder / "scripts"
        try:
            module = _load_module(module_name, scripts_dir)
            func = getattr(module, func_name)
            result = func(url)
            if returns_list:
                observations.extend(result)
            else:
                observations.append(result)
            logger.info("%s.%s completed", skill_name, module_name)
        except Exception as exc:  # noqa: BLE001 - one failed check must not crash the audit
            logger.warning("%s.%s failed: %s", skill_name, module_name, exc)
            observations.append(
                Observation(
                    id=f"{module_name}-error",
                    skill=skill_name,
                    category="error",
                    description=f"{module_name} could not be completed.",
                    data={"checked": False, "error": str(exc)},
                )
            )

    return observations