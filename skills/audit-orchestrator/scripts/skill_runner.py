"""
Skill runner for audit-orchestrator.

Dynamically imports each specialist skill's check functions - skill folder
names contain hyphens, so they can't be imported as normal Python packages
- and runs them all against a single validated URL, returning every
skill's Observations as one combined list.

Rendering-dependent checks for the HOMEPAGE share ONE Playwright render
pass via common.fetch_utils.full_render_session (Step 12).

Step 22 adds MULTI-PAGE crawling: page_discovery finds a bounded set of
representative internal pages (about/pricing/products/etc. - see
page_discovery.py, Step 21), and up to MAX_PAGES_TO_AUDIT of them are each
given their own lighter audit (render diff + structured data only - NOT
OCR, date signals, entity signals, or engagement checks, and NO additional
LLM calls) via their own independent render. This still produces only
Observations that flow into the SAME single main reasoning call - total
Gemini calls per audit stays at 2 regardless of how many pages are looked
at, which matters given the confirmed 20-requests/day free-tier limit.

One failing check (or failing secondary page) must never crash the whole
audit: each is wrapped individually, and a failure is recorded as an
error Observation rather than propagated.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = PROJECT_ROOT / "skills"

sys.path.insert(0, str(PROJECT_ROOT))
from common.fetch_utils import fetch_raw_html, fetch_rendered_html, full_render_session  # noqa: E402
from common.schema import Observation  # noqa: E402

logger = logging.getLogger("audit-orchestrator.skill_runner")

# Runtime-budget decision (Step 22): audit at most this many discovered
# secondary pages, even if more were found. Keeps total audit time
# comfortably within the 5-minute budget - each secondary page needs its
# own Playwright launch.
MAX_PAGES_TO_AUDIT = 2


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


def _fetch_secondary_page(url: str) -> tuple[str | None, str | None, str | None]:
    """
    Fetch raw + rendered HTML for a secondary (non-homepage) page.
    Returns (raw_html, rendered_html, error). raw_html failing is
    non-fatal (structured_data_checks can work from rendered_html alone);
    rendered_html failing means the page can't be audited at all.
    """
    raw_html: str | None = None
    try:
        raw_html = fetch_raw_html(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Secondary page raw fetch failed for %s: %s", url, exc)

    try:
        rendered_html = fetch_rendered_html(url)
    except Exception as exc:  # noqa: BLE001
        return raw_html, None, str(exc)

    return raw_html, rendered_html, None


def _run_secondary_page_checks(
    page_info: Dict[str, str], render_checks_module, structured_data_checks_module
) -> List[Observation]:
    """
    Run a lighter audit (render diff + structured data ONLY) against one
    discovered secondary page. No OCR, no date/entity/engagement checks,
    no additional LLM calls - keeps runtime and Gemini usage bounded
    regardless of how many pages are found.
    """
    page_url = page_info["url"]
    category = page_info["category"]
    observations: List[Observation] = []

    raw_html, rendered_html, error = _fetch_secondary_page(page_url)

    if rendered_html is None:
        return [
            _error_observation(
                f"secondary-page-{category}-error",
                "crawl-render-audit",
                f"Could not audit secondary page ({category}): {page_url}",
                error or "unknown rendering error",
            )
        ]

    if raw_html is not None:
        diff_data: Dict[str, Any] = render_checks_module.compute_render_diff(raw_html, rendered_html)
        diff_data["page_url"] = page_url
        diff_data["page_category"] = category
        observations.append(
            Observation(
                id=f"secondary-page-{category}-render-diff",
                skill="crawl-render-audit",
                category="rendering",
                description=f"Raw-vs-rendered content diff for secondary page ({category}): {page_url}",
                data=diff_data,
            )
        )

    raw_structured = (
        structured_data_checks_module.extract_structured_data(raw_html, page_url)
        if raw_html is not None
        else None
    )
    rendered_structured = structured_data_checks_module.extract_structured_data(rendered_html, page_url)
    observations.append(
        Observation(
            id=f"secondary-page-{category}-structured-data",
            skill="crawl-render-audit",
            category="structured_data",
            description=f"Structured data presence for secondary page ({category}): {page_url}",
            data={
                "page_url": page_url,
                "page_category": category,
                "raw": raw_structured,
                "rendered": rendered_structured,
            },
        )
    )
    return observations


def run_all_specialist_skills(url: str) -> List[Observation]:
    """Run every implemented check across all three specialist skills."""
    observations: List[Observation] = []

    crawl_scripts = SKILLS_ROOT / "crawl-render-audit" / "scripts"
    freshness_scripts = SKILLS_ROOT / "freshness-corroboration" / "scripts"
    engagement_scripts = SKILLS_ROOT / "engagement-audit" / "scripts"

    # --- Checks that don't need rendering: run independently ---
    robots_disallowed_paths: List[str] = []
    try:
        access_checks = _load_module("access_checks", crawl_scripts)
        access_observations = access_checks.run_access_checks(url)
        observations.extend(access_observations)
        for obs in access_observations:
            if obs.id == "crawl-robots-txt":
                robots_disallowed_paths = obs.data.get("disallowed_paths", [])
                break
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
    # must load before image_checks (sibling import). ---
    try:
        render_checks = _load_module("render_checks", crawl_scripts)
        structured_data_checks = _load_module("structured_data_checks", crawl_scripts)
        image_checks = _load_module("image_checks", crawl_scripts)
        page_discovery = _load_module("page_discovery", crawl_scripts)
        date_signals = _load_module("date_signals", freshness_scripts)
        entity_signals = _load_module("entity_signals", freshness_scripts)
        engagement_checks = _load_module("engagement_checks", engagement_scripts)
        intent_alignment = _load_module("intent_alignment", engagement_scripts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load one or more rendering-dependent check modules: %s", exc)
        observations.append(
            _error_observation(
                "module-load-error", "audit-orchestrator",
                "Could not load rendering-dependent check modules.", str(exc),
            )
        )
        return observations

    # --- One shared render pass for the homepage, used by all homepage checks ---
    discovered_pages: List[Dict[str, str]] = []
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
                page_discovery_obs = page_discovery.run_page_discovery(
                    url,
                    rendered_html=render.rendered_html,
                    final_url=render.final_url,
                    disallowed_paths=robots_disallowed_paths,
                )
                observations.append(page_discovery_obs)
                discovered_pages = page_discovery_obs.data.get("discovered_pages", [])
                logger.info(
                    "crawl-render-audit.page_discovery completed (%d pages found)",
                    len(discovered_pages),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("crawl-render-audit.page_discovery failed: %s", exc)
                observations.append(
                    _error_observation(
                        "page-discovery-error", "crawl-render-audit",
                        "page_discovery could not be completed.", str(exc),
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
                observations.append(
                    entity_signals.run_entity_signal_checks(url, rendered_html=render.rendered_html)
                )
                logger.info("freshness-corroboration.entity_signals completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("freshness-corroboration.entity_signals failed: %s", exc)
                observations.append(
                    _error_observation(
                        "entity-signals-error", "freshness-corroboration",
                        "entity_signals could not be completed.", str(exc),
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

            try:
                observations.append(
                    intent_alignment.run_intent_alignment_check(
                        url,
                        rendered_html=render.rendered_html,
                        above_fold_text=render.above_fold_text,
                    )
                )
                logger.info("engagement-audit.intent_alignment completed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("engagement-audit.intent_alignment failed: %s", exc)
                observations.append(
                    _error_observation(
                        "intent-alignment-error", "engagement-audit",
                        "intent_alignment could not be completed.", str(exc),
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
                    "page-discovery-error", "crawl-render-audit",
                    "page_discovery could not be completed.", error,
                ),
                _error_observation(
                    "date-signals-error", "freshness-corroboration",
                    "date_signals could not be completed.", error,
                ),
                _error_observation(
                    "entity-signals-error", "freshness-corroboration",
                    "entity_signals could not be completed.", error,
                ),
                _error_observation(
                    "engagement-checks-error", "engagement-audit",
                    "engagement_checks could not be completed.", error,
                ),
                _error_observation(
                    "intent-alignment-error", "engagement-audit",
                    "intent_alignment could not be completed.", error,
                ),
            ]
        )

    # --- Multi-page crawling (Step 22): audit up to MAX_PAGES_TO_AUDIT of
    # the discovered secondary pages, each independently rendered and
    # fault-isolated. No additional LLM calls - all evidence still flows
    # into the single main reasoning call. ---
    for page_info in discovered_pages[:MAX_PAGES_TO_AUDIT]:
        try:
            page_observations = _run_secondary_page_checks(
                page_info, render_checks, structured_data_checks
            )
            observations.extend(page_observations)
            logger.info(
                "crawl-render-audit.secondary_page_checks completed for %s (%s)",
                page_info["url"], page_info["category"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Secondary page check failed for %s: %s", page_info["url"], exc)
            observations.append(
                _error_observation(
                    f"secondary-page-{page_info.get('category', 'unknown')}-error",
                    "crawl-render-audit",
                    f"Could not audit secondary page: {page_info.get('url', 'unknown')}",
                    str(exc),
                )
            )

    return observations