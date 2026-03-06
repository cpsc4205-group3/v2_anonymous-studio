"""Large-dataset plumbing stress check for Anonymous Studio.

This script validates the chunking/progress pipeline path quickly by stubbing
the anonymization call (so runtime is not dominated by NLP model speed).
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tasks


def _run_df_stress(rows: int) -> None:
    df = pd.DataFrame({"text": ["Alice at Seattle clinic"] * rows})
    cfg = {
        "job_id": "make-stress-df",
        "operator": "replace",
        "entities": ["PERSON"],
        "threshold": 0.35,
        "text_columns": ["text"],
        "chunk_size": 5000,
    }
    t0 = time.time()
    out, stats = tasks.run_pii_anonymization(df, cfg)
    dt = time.time() - t0
    status = tasks.PROGRESS_REGISTRY.get("make-stress-df", {}).get("status")
    if len(out) != rows or stats["processed_rows"] != rows or status != "done":
        raise SystemExit("DF stress check failed")
    print(f"DF rows={rows} duration_s={dt:.2f} rows_per_s={int(rows / dt) if dt else 0}")


def _run_mongo_shape_stress(rows: int) -> None:
    mongo_like = [SimpleNamespace(_id=str(i), text="Alice from Austin") for i in range(rows)]
    cfg = {
        "job_id": "make-stress-mongo",
        "operator": "replace",
        "entities": ["PERSON"],
        "threshold": 0.35,
        "text_columns": ["text"],
        "chunk_size": 5000,
    }
    t0 = time.time()
    out, stats = tasks.run_pii_anonymization(mongo_like, cfg)
    dt = time.time() - t0
    status = tasks.PROGRESS_REGISTRY.get("make-stress-mongo", {}).get("status")
    if len(out) != rows or stats["processed_rows"] != rows or status != "done":
        raise SystemExit("Mongo-shape stress check failed")
    if "_id" in out.columns:
        raise SystemExit("_id should not appear in coerced output")
    print(f"Mongo-shape rows={rows} duration_s={dt:.2f} rows_per_s={int(rows / dt) if dt else 0}")


def main() -> None:
    # Fast anonymization stub so we stress pipeline plumbing, not NLP model speed.
    def fast_anonymize(series, engine, entities, operator, threshold):
        out = series.str.replace("Alice", "[PERSON]", regex=False)
        return out, {"PERSON": int(series.notna().sum())}

    tasks._anonymize_series = fast_anonymize

    rows_df = int(os.environ.get("STRESS_ROWS_DF", "300000"))
    rows_mongo = int(os.environ.get("STRESS_ROWS_MONGO", "250000"))
    _run_df_stress(rows_df)
    _run_mongo_shape_stress(rows_mongo)
    print("Stress plumbing checks passed.")


if __name__ == "__main__":
    main()
