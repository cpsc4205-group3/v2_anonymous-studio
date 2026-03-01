"""
Anonymous Studio — taipy.core Configuration
Declares every DataNode, Task, and Scenario, then boots the Orchestrator.

Execution modes  (set env var ANON_MODE):
  development  -> synchronous single-process  (default — works everywhere)
  standalone   -> true multi-process workers  (set for production)

Config strategy:
  1. Load structural layout from config.toml  (ships with the project)
  2. Patch in the actual Python function reference at runtime
  3. Generate config.toml automatically if one is missing

Why toml + runtime patch?
  config.toml lets Taipy validate structure independently of Python imports.
  The function callable must be resolved at runtime regardless, so we patch
  it after loading. If config.toml is missing we fall back to pure-Python
  Config.configure_* calls and regenerate the file automatically.
"""
from __future__ import annotations
import os
import sys
from typing import Optional

from taipy import Config
from taipy.common.config.common.scope import Scope
from tasks import run_pii_anonymization

# ---- Execution mode ---------------------------------------------------------
MODE    = os.environ.get("ANON_MODE", "development")
WORKERS = int(os.environ.get("ANON_WORKERS", "4"))

# ---- Storage ----------------------------------------------------------------
STORAGE = os.environ.get("ANON_STORAGE", "/tmp/anon_studio")
os.makedirs(STORAGE, exist_ok=True)

# ---- Config file path -------------------------------------------------------
_HERE        = os.path.dirname(os.path.abspath(__file__))
_CONFIG_TOML = os.path.join(_HERE, "config.toml")


def _register_configs():
    """
    Register all DataNode / Task / Scenario configs programmatically.
    (config.toml is kept for Taipy Studio / documentation only — not loaded
    at runtime because Taipy 4.x does not convert TOML scope strings to Scope
    enums automatically, which causes validation errors.)
    """
    raw_input_cfg = Config.configure_pickle_data_node(
        id="raw_input", scope=Scope.SCENARIO,
    )
    job_config_cfg = Config.configure_pickle_data_node(
        id="job_config", scope=Scope.SCENARIO,
    )
    anon_output_cfg = Config.configure_pickle_data_node(
        id="anon_output", scope=Scope.SCENARIO,
    )
    job_stats_cfg = Config.configure_pickle_data_node(
        id="job_stats", scope=Scope.SCENARIO,
    )
    task_cfg = Config.configure_task(
        id="anonymize_task",
        function=run_pii_anonymization,
        input=[raw_input_cfg, job_config_cfg],
        output=[anon_output_cfg, job_stats_cfg],
        skippable=False,
    )
    Config.configure_scenario(
        id="pii_pipeline",
        task_configs=[task_cfg],
    )


def _configure_jobs():
    if MODE == "standalone":
        Config.configure_job_executions(mode="standalone",
                                        max_nb_of_workers=WORKERS)
    else:
        Config.configure_job_executions(mode="development")


# Run at import time
_register_configs()
_configure_jobs()

# ---- Validate — fail loud rather than "no configs found" --------------------
_missing = {"pii_pipeline"} - set(Config.scenarios.keys())
if _missing:
    raise RuntimeError(
        f"\n[AnonymousStudio] taipy.core config incomplete — missing: {_missing}\n"
        f"  Registered scenarios: {list(Config.scenarios.keys())}\n\n"
        "  Most likely causes:\n"
        "  1. tasks.py or pii_engine.py has an import error\n"
        "     -> Run: python -c 'import tasks' to see the traceback\n"
        "  2. Running from the wrong directory\n"
        "     -> cd into the anonymous_studio/ folder before running\n"
        "  3. Virtual environment not activated\n"
        "     -> Run: source .venv/bin/activate\n"
    )

# ---- Expose scenario config for submit_job ----------------------------------
pii_scenario_cfg = Config.scenarios["pii_pipeline"]

# =============================================================================
#  ORCHESTRATOR
# =============================================================================
from taipy.core import Orchestrator as _Orch
import taipy.core as tc

_orchestrator: Optional[_Orch] = None


def start_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = _Orch()
        _orchestrator.run(force_restart=True)
    return _orchestrator


def stop_orchestrator():
    global _orchestrator
    if _orchestrator:
        _orchestrator.stop()
        _orchestrator = None


def submit_job(raw_df, config: dict):
    """Create a fresh Scenario, write inputs, submit to the Orchestrator."""
    sc  = tc.create_scenario(pii_scenario_cfg)
    sc.raw_input.write(raw_df)
    sc.job_config.write(config)
    sub = tc.submit(sc)
    return sc, sub


def get_job_for_scenario(scenario_id: str):
    """Return the latest Job for a given scenario id, or None."""
    for j in reversed(tc.get_jobs()):
        try:
            parents = tc.get_parents(j)
            for p in parents.get("scenarios", []):
                if str(p.id) == scenario_id:
                    return j
        except Exception:
            pass
    return None