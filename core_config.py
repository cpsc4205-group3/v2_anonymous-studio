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
import warnings
import tempfile
from urllib.parse import parse_qs, unquote, urlparse
from datetime import timedelta
import pandas as pd

from taipy import Config, Frequency
from taipy.common.config.common.scope import Scope
from tasks import run_pii_anonymization
from taipy.core.common.mongo_default_document import MongoDefaultDocument

# ---- Execution mode ---------------------------------------------------------
MODE = (os.environ.get("ANON_MODE", "development") or "development").strip().lower()
if MODE not in ("development", "standalone"):
    warnings.warn(
        f"[AnonymousStudio] Unrecognised ANON_MODE='{MODE}'. Falling back to 'development'.",
        UserWarning, stacklevel=1,
    )
    MODE = "development"

try:
    WORKERS = max(1, int(os.environ.get("ANON_WORKERS", "4") or "4"))
except ValueError:
    warnings.warn("[AnonymousStudio] ANON_WORKERS is not a valid integer. Using 4.", UserWarning, stacklevel=1)
    WORKERS = 4

RAW_INPUT_BACKEND = (os.environ.get("ANON_RAW_INPUT_BACKEND", "auto") or "auto").strip().lower()

try:
    MONGO_WRITE_BATCH = max(500, int(os.environ.get("ANON_MONGO_WRITE_BATCH", "5000") or "5000"))
except ValueError:
    warnings.warn("[AnonymousStudio] ANON_MONGO_WRITE_BATCH is not a valid integer. Using 5000.", UserWarning, stacklevel=1)
    MONGO_WRITE_BATCH = 5000

# ---- Storage ----------------------------------------------------------------
_DEFAULT_STORAGE = os.path.join(tempfile.gettempdir(), "anon_studio")
STORAGE = os.environ.get("ANON_STORAGE", _DEFAULT_STORAGE)
os.makedirs(STORAGE, exist_ok=True)

# ---- Config file path -------------------------------------------------------
_HERE        = os.path.dirname(os.path.abspath(__file__))
_CONFIG_TOML = os.path.join(_HERE, "config.toml")

# ---- Core service config ----------------------------------------------------
CORE_MODE = os.environ.get("ANON_CORE_MODE", "development").lower()
if CORE_MODE not in ("development", "experiment"):
    CORE_MODE = "development"
Config.configure_core(
    root_folder=STORAGE,
    storage_folder=".taipy_core/",
    taipy_storage_folder=os.path.join(STORAGE, ".taipy"),
    read_entity_retry=int(os.environ.get("ANON_READ_ENTITY_RETRY", "2")),
    mode=CORE_MODE,
)


def _compare_job_stats(*stats_values):
    rows = []
    for idx, stats in enumerate(stats_values, start=1):
        safe = stats if isinstance(stats, dict) else {}
        processed = int(safe.get("processed_rows", 0) or 0)
        entities = int(safe.get("total_entities", 0) or 0)
        rows.append({
            "Scenario": f"Scenario {idx}",
            "Processed Rows": processed,
            "Entities": entities,
            "Entities / Row": round((entities / processed), 3) if processed else 0.0,
        })
    return pd.DataFrame(rows)


def _register_configs():
    """
    Register all DataNode / Task / Scenario configs programmatically.
    (config.toml is kept for Taipy Studio / documentation only — not loaded
    at runtime because Taipy 4.x does not convert TOML scope strings to Scope
    enums automatically, which causes validation errors.)

    Security note — raw_input DataNode:
        raw_input backend is selected by ANON_RAW_INPUT_BACKEND:
        - development defaults to in-memory (no raw PII at rest)
        - standalone defaults to Mongo-backed persistence
        Avoid pickle backend unless you fully trust the environment.
    """
    raw_input_cfg = _configure_raw_input_data_node()
    job_config_cfg = Config.configure_pickle_data_node(
        id="job_config",
        scope=Scope.SCENARIO,
        validity_period=timedelta(days=1),
    )
    anon_output_cfg = Config.configure_pickle_data_node(
        id="anon_output",
        scope=Scope.SCENARIO,
        validity_period=timedelta(days=14),
    )
    job_stats_cfg = Config.configure_pickle_data_node(
        id="job_stats",
        scope=Scope.SCENARIO,
        validity_period=timedelta(days=14),
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
        frequency=Frequency.WEEKLY,
        comparators={
            job_stats_cfg.id: _compare_job_stats,
        },
    )


def _configure_jobs():
    if MODE == "standalone":
        Config.configure_job_executions(
            mode="standalone",
            max_nb_of_workers=WORKERS,
        )
        return
    if MODE == "cluster":
        warnings.warn(
            "[AnonymousStudio] ANON_MODE=cluster is not a supported community mode. "
            "Using standalone workers instead.",
            UserWarning,
            stacklevel=1,
        )
        Config.configure_job_executions(
            mode="standalone",
            max_nb_of_workers=WORKERS,
        )
        return
    Config.configure_job_executions(mode="development")


def _parse_extra_args(raw: str):
    pairs = [p.strip() for p in raw.split(",") if p.strip()]
    out = {}
    for pair in pairs:
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _mongo_config_from_env():
    """Build kwargs for configure_mongo_collection_data_node from env vars."""
    uri = (os.environ.get("ANON_MONGO_URI") or os.environ.get("MONGODB_URI") or "").strip()
    cfg = {
        "db_name": (os.environ.get("ANON_MONGO_DB") or "").strip(),
        "collection_name": (os.environ.get("ANON_MONGO_COLLECTION") or "raw_input").strip(),
        "db_username": (os.environ.get("ANON_MONGO_USER") or "").strip(),
        "db_password": (os.environ.get("ANON_MONGO_PASSWORD") or "").strip(),
        "db_host": (os.environ.get("ANON_MONGO_HOST") or "localhost").strip(),
        "db_port": int((os.environ.get("ANON_MONGO_PORT") or "27017").strip()),
        "db_driver": (os.environ.get("ANON_MONGO_DRIVER") or "").strip(),
        "db_extra_args": _parse_extra_args((os.environ.get("ANON_MONGO_EXTRA_ARGS") or "").strip()),
        "custom_document": MongoDefaultDocument,
        "scope": Scope.SCENARIO,
        "validity_period": timedelta(hours=2),
    }

    if uri:
        parsed = urlparse(uri)
        if parsed.scheme not in ("mongodb", "mongodb+srv"):
            raise RuntimeError(
                "[AnonymousStudio] ANON_MONGO_URI/MONGODB_URI must start with mongodb:// or mongodb+srv://"
            )
        if parsed.username:
            cfg["db_username"] = unquote(parsed.username)
        if parsed.password:
            cfg["db_password"] = unquote(parsed.password)
        if parsed.hostname:
            cfg["db_host"] = parsed.hostname
        if parsed.port:
            cfg["db_port"] = int(parsed.port)
        if parsed.scheme == "mongodb+srv":
            cfg["db_driver"] = "srv"
        path_db = (parsed.path or "").lstrip("/")
        if path_db:
            cfg["db_name"] = path_db
        query_args = {
            k: v[0] for k, v in parse_qs(parsed.query).items() if v
        }
        if query_args:
            cfg["db_extra_args"] = {**cfg["db_extra_args"], **query_args}

    if not cfg["db_name"]:
        raise RuntimeError(
            "[AnonymousStudio] Mongo backend selected but ANON_MONGO_DB is empty. "
            "Set ANON_MONGO_DB or provide a database in ANON_MONGO_URI/MONGODB_URI."
        )
    return cfg


def _resolve_raw_input_backend() -> str:
    backend = RAW_INPUT_BACKEND
    valid = {"auto", "memory", "mongo", "pickle"}
    if backend not in valid:
        warnings.warn(
            f"[AnonymousStudio] Invalid ANON_RAW_INPUT_BACKEND='{backend}'. Using auto.",
            UserWarning,
            stacklevel=1,
        )
        backend = "auto"

    if backend == "auto":
        return "memory" if MODE == "development" else "mongo"
    return backend


def _configure_raw_input_data_node():
    backend = _resolve_raw_input_backend()
    if backend == "memory":
        if MODE != "development":
            raise RuntimeError(
                "[AnonymousStudio] In-memory raw_input DataNode is only safe in ANON_MODE=development. "
                "Use ANON_RAW_INPUT_BACKEND=mongo (recommended) or ANON_RAW_INPUT_BACKEND=pickle."
            )
        return Config.configure_in_memory_data_node(
            id="raw_input",
            scope=Scope.SCENARIO,
        )
    if backend == "mongo":
        mongo_kwargs = _mongo_config_from_env()
        return Config.configure_mongo_collection_data_node(
            id="raw_input",
            **mongo_kwargs,
        )
    if backend == "pickle":
        warnings.warn(
            "[AnonymousStudio] raw_input uses pickle backend; avoid this for untrusted environments.",
            UserWarning,
            stacklevel=1,
        )
        return Config.configure_pickle_data_node(
            id="raw_input",
            scope=Scope.SCENARIO,
            validity_period=timedelta(hours=2),
        )
    raise RuntimeError(f"[AnonymousStudio] Unsupported raw_input backend '{backend}'.")


def _apply_override_config():
    """Apply optional TOML override from environment."""
    cfg_path = os.environ.get("TAIPY_CONFIG_PATH") or os.environ.get("ANON_CONFIG_PATH")
    if not cfg_path:
        return
    if not os.path.exists(cfg_path):
        warnings.warn(
            f"[AnonymousStudio] TAIPY_CONFIG_PATH not found: {cfg_path}",
            UserWarning,
            stacklevel=1,
        )
        return
    Config.override(cfg_path)


# Run at import time
_register_configs()
_configure_jobs()
_apply_override_config()
Config.check()

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

import taipy.core as tc


def submit_job(raw_df, config: dict):
    """Create a fresh Scenario, write inputs, submit to the Orchestrator."""
    sc  = tc.create_scenario(pii_scenario_cfg)
    backend = _resolve_raw_input_backend()

    def _normalize_mongo_value(value):
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return value

    def _to_mongo_docs(records):
        docs = []
        for rec in records:
            if isinstance(rec, MongoDefaultDocument):
                docs.append(rec)
                continue
            if hasattr(rec, "__dict__") and not isinstance(rec, dict):
                rec = dict(rec.__dict__)
            if not isinstance(rec, dict):
                rec = {"value": rec}
            normalized = {str(k): _normalize_mongo_value(v) for k, v in rec.items()}
            docs.append(MongoDefaultDocument(**normalized))
        return docs

    if backend == "mongo":
        # Taipy MongoCollectionDataNode expects custom document instances.
        # We stream in batches via append() to avoid a giant intermediate payload.
        if isinstance(raw_df, pd.DataFrame):
            total = len(raw_df)
            if total == 0:
                sc.raw_input.write([])
            else:
                first = True
                for start in range(0, total, MONGO_WRITE_BATCH):
                    stop = min(start + MONGO_WRITE_BATCH, total)
                    docs = _to_mongo_docs(raw_df.iloc[start:stop].to_dict("records"))
                    if first:
                        sc.raw_input.write(docs)
                        first = False
                    else:
                        sc.raw_input.append(docs)
        elif isinstance(raw_df, list):
            if not raw_df:
                sc.raw_input.write([])
            elif len(raw_df) <= MONGO_WRITE_BATCH:
                sc.raw_input.write(_to_mongo_docs(raw_df))
            else:
                sc.raw_input.write(_to_mongo_docs(raw_df[:MONGO_WRITE_BATCH]))
                for start in range(MONGO_WRITE_BATCH, len(raw_df), MONGO_WRITE_BATCH):
                    sc.raw_input.append(_to_mongo_docs(raw_df[start:start + MONGO_WRITE_BATCH]))
        elif isinstance(raw_df, dict):
            sc.raw_input.write(_to_mongo_docs([raw_df]))
        else:
            sc.raw_input.write(_to_mongo_docs([raw_df]))
    else:
        sc.raw_input.write(raw_df)
    sc.job_config.write(config)
    sub = tc.submit(sc)
    return sc, sub


def get_job_for_scenario(scenario_id: str):
    """Return the latest Job for a given scenario id, or None."""
    scenario_id = str(scenario_id)
    for j in reversed(tc.get_jobs()):
        try:
            submit_entity_id = str(
                getattr(j, "submit_entity_id", None)
                or getattr(j, "_submit_entity_id", None)
                or ""
            )
            if submit_entity_id and submit_entity_id == scenario_id:
                return j
        except Exception:
            continue
        # Backward-compat fallback for older Taipy APIs.
        try:
            parents = tc.get_parents(j)
            for p in parents.get("scenarios", []):
                if str(p.id) == scenario_id:
                    return j
        except Exception:
            pass
    return None
