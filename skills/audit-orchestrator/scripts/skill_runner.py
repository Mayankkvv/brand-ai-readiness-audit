"""
Skill runner for audit-orchestrator.

Dynamically imports each specialist skill's check functions - skill folder
names contain hyphens, so they can't be imported as normal Python packages
- and runs them all against a single validated URL, returning every
skill's Observations as one combined list.

Rendering-dependent checks (render diff, structured data, image OCR, date
signals, engagement checks) share ONE Playwright render pass via
common.fetch_utils.full_render_session (Step 12), instead of each
independently launching its own browser session. This was added after
real-world testing showed 5 separate per-audit renders of the same page
caused intermittent timeouts and unnecessary runtime overhead.

One failing check must never crash the whole audit: each check is wrapped
individually, and a failure is recorded as an error Observation rather
than propagated. If the shared render itself fails, every rendering-
dependent check becomes an error Observation, but access_checks (which
needs no rendering) still runs and reports normally.
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
from common.fetch_utils import full_render_session  # noqa: E402
from common.schema import Observation  # noqa: E402

logger = logging.getLogger("audit-orchestrator.skill_runner")


def _load_module(module_name: str, scripts_dir: Path) -> types.ModuleType:
    """
    Import a skill script module by file path, adding its scripts/
    directory to sys.path first so any sibling imports inside that module
    (e.g. image_checks.py importing render_checks.py) resolve correctly,
    exactly as they do when that script is run standalone.
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


def _error_observation(obs_id: str, skill: str, description: str, error: str) -> Observation:
    return Observation(
        id=obs_id,
        skill=skill,
        category="error",
        description=description,
        data={"checked": False, "error": error},
    )


def run_all_specialist_skills(url: str) -> List[Observation]:
    """Run every implemented check across all three specialist skills."""
    observations: List[Observation] = []

    crawl_scripts = SKILLS_ROOT / "crawl-render-audit" / "scripts"
    freshness_scripts = SKILLS_ROOT / "freshness-corroboration" / "scripts"
    engagement_scripts = SKILLS_ROOT / "engagement-audit" / "scripts"

    # --- Checks that don't need rendering: run independently ---
    try:
        access_checks = _load_module("access_checks", crawl_scripts)
        observations.extend(access_checks.run_access_checks(url))
        logger.info("crawl-render-audit.access_checks completed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("crawl-render-audit.access_checks failed: %s", exc)
        observations.append(
            _error_observation(
                "access-checks-error", "crawl-render-audit",
                "access_checks could not be completed.", str(exc),
            )
        )

    # --- Load rendering-dependent check modules. Order matters: render_checks
    # must load before image_checks, since image_checks.py does
    # `from render_checks import extract_visible_text` as a sibling import. ---
    try:
        render_checks = _load_module("render_checks", crawl_scripts)
        structured_data_checks = _load_module("structured_data_checks", crawl_scripts)
        image_checks = _load_module("image_checks", crawl_scripts)
        date_signals = _load_module("date_signals", freshness_scripts)
        engagement_checks = _load_module("engagement_checks", engagement_scripts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load one or more rendering-dependent check modules: %s", exc)
        observations.append(
            _error_observation(
                "module-load-error", "audit-orchestrator",
                "Could not load rendering-dependent check modules.", str(exc),
            )
        )
        return observations

    # --- One shared render pass, used by all five rendering-dependent checks ---
    try:
        with full_render_session(url) as render:
            try:
                observations.append(
                    render_checks.run_render_checks(
                        url, raw_html=render.raw_html, rendered_html=render.rendered_html
                    )
                )
                logger.info("crawl-render-audit.render_checks completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("crawl-render-audit.render_checks failed: %s", exc)
                observations.append(
                    _error_observation(
                        "render-checks-error", "crawl-render-audit",
                        "render_checks could not be completed.", str(exc),
                    )
                )

            try:
                observations.append(
                    structured_data_checks.run_structured_data_checks(
                        url, raw_html=render.raw_html, rendered_html=render.rendered_html
                    )
                )
                logger.info("crawl-render-audit.structured_data_checks completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("crawl-render-audit.structured_data_checks failed: %s", exc)
                observations.append(
                    _error_observation(
                        "structured-data-checks-error", "crawl-render-audit",
                        "structured_data_checks could not be completed.", str(exc),
                    )
                )

            try:
                observations.append(
                    image_checks.run_image_text_checks(
                        url, rendered_html=render.rendered_html, context=render.context
                    )
                )
                logger.info("crawl-render-audit.image_checks completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("crawl-render-audit.image_checks failed: %s", exc)
                observations.append(
                    _error_observation(
                        "image-checks-error", "crawl-render-audit",
                        "image_checks could not be completed.", str(exc),
                    )
                )

            try:
                observations.append(
                    date_signals.run_date_signal_checks(url, rendered_html=render.rendered_html)
                )
                logger.info("freshness-corroboration.date_signals completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("freshness-corroboration.date_signals failed: %s", exc)
                observations.append(
                    _error_observation(
                        "date-signals-error", "freshness-corroboration",
                        "date_signals could not be completed.", str(exc),
                    )
                )

            try:
                observations.extend(
                    engagement_checks.run_engagement_checks(
                        url,
                        rendered_html=render.rendered_html,
                        above_fold_text=render.above_fold_text,
                    )
                )
                logger.info("engagement-audit.engagement_checks completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("engagement-audit.engagement_checks failed: %s", exc)
                observations.append(
                    _error_observation(
                        "engagement-checks-error", "engagement-audit",
                        "engagement_checks could not be completed.", str(exc),
                    )
                )

    except Exception as exc:  # noqa: BLE001 - the shared render itself failed
        logger.warning("Shared render session failed for %s: %s", url, exc)
        error = f"shared render failed: {exc}"
        observations.extend(
            [
                _error_observation(
                    "render-checks-error", "crawl-render-audit",
                    "render_checks could not be completed.", error,
                ),
                _error_observation(
                    "structured-data-checks-error", "crawl-render-audit",
                    "structured_data_checks could not be completed.", error,
                ),
                _error_observation(
                    "image-checks-error", "crawl-render-audit",
                    "image_checks could not be completed.", error,
                ),
                _error_observation(
                    "date-signals-error", "freshness-corroboration",
                    "date_signals could not be completed.", error,
                ),
                _error_observation(
                    "engagement-checks-error", "engagement-audit",
                    "engagement_checks could not be completed.", error,
                ),
            ]
        )

    return observations