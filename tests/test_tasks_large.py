from __future__ import annotations

import os
import tempfile
import time
from types import SimpleNamespace

import pandas as pd

import tasks
from services.jobs import build_job_config


def test_large_dataframe_processing_completes_with_chunking(monkeypatch):
    rows = 200_000
    df = pd.DataFrame({"text": ["Alice at Seattle clinic"] * rows})

    def fast_anonymize(series, engine, entities, operator, threshold):
        out = series.str.replace("Alice", "[PERSON]", regex=False)
        return out, {"PERSON": int(series.notna().sum())}

    monkeypatch.setattr(tasks, "_anonymize_series", fast_anonymize)
    cfg = {
        "job_id": "stress-large-df",
        "operator": "replace",
        "entities": ["PERSON"],
        "threshold": 0.35,
        "text_columns": ["text"],
        "chunk_size": 5_000,
    }

    t0 = time.time()
    out, stats = tasks.run_pii_anonymization(df, cfg)
    elapsed = time.time() - t0

    assert len(out) == rows
    assert stats["processed_rows"] == rows
    assert stats["total_entities"] == rows
    assert tasks.PROGRESS_REGISTRY["stress-large-df"]["status"] == "done"
    # Guardrail only: this validates no pathological slowdown in chunk plumbing.
    assert elapsed < 15.0


def test_mongo_like_documents_are_coerced_without_object_id_column():
    mongo_like = [
        {"_id": "abc", "text": "Seattle office"},
        SimpleNamespace(_id="def", text="Austin clinic"),
    ]

    df = tasks._coerce_raw_input_to_df(mongo_like)

    assert len(df) == 2
    assert "text" in df.columns
    assert "_id" not in df.columns


def test_progress_updates_are_written_to_durable_snapshot(monkeypatch):
    captured = {}

    def fake_write(job_id, payload):
        captured["job_id"] = job_id
        captured["payload"] = dict(payload)
        return payload

    monkeypatch.setattr(tasks, "write_progress_snapshot", fake_write)
    tasks._progress("job-snap", 12.5, 5, 40, "Chunk 1/8", "running")

    assert captured["job_id"] == "job-snap"
    assert captured["payload"]["pct"] == 12.5
    assert captured["payload"]["processed"] == 5
    assert captured["payload"]["total"] == 40
    assert captured["payload"]["status"] == "running"
    assert "updated_at" in captured["payload"]


def test_build_job_config_includes_spacy_model():
    cfg = build_job_config(
        job_id="cfg-model",
        operator="replace",
        entities=["EMAIL_ADDRESS"],
        threshold=0.35,
        chunk_size=500,
        spacy_model="en_core_web_sm",
    )
    assert cfg["spacy_model"] == "en_core_web_sm"
    assert cfg["compute_backend"] in {"auto", "pandas", "dask"}
    assert int(cfg["dask_min_rows"]) >= 10000


def test_run_task_applies_requested_spacy_model(monkeypatch):
    import pii_engine

    seen = {}

    def fake_set_spacy_model(choice):
        seen["choice"] = choice
        return "en_core_web_sm", True, "ok"

    def fake_get_engine():
        return object()

    def fast_anonymize(series, engine, entities, operator, threshold):
        return series, {}

    monkeypatch.setattr(pii_engine, "set_spacy_model", fake_set_spacy_model)
    monkeypatch.setattr(pii_engine, "get_engine", fake_get_engine)
    monkeypatch.setattr(tasks, "_anonymize_series", fast_anonymize)

    out, stats = tasks.run_pii_anonymization(
        pd.DataFrame({"text": ["john@example.com"]}),
        {
            "job_id": "job-model-select",
            "operator": "replace",
            "entities": ["EMAIL_ADDRESS"],
            "threshold": 0.35,
            "text_columns": ["text"],
            "chunk_size": 100,
            "spacy_model": "en_core_web_sm",
        },
    )

    assert len(out) == 1
    assert seen["choice"] == "en_core_web_sm"
    assert stats["spacy_model_requested"] == "en_core_web_sm"
    assert stats["spacy_model_resolved"] == "en_core_web_sm"
    assert stats["spacy_has_ner"] is True


def test_run_task_dask_request_falls_back_when_not_installed(monkeypatch):
    import pii_engine

    def fake_set_spacy_model(choice):
        return "en_core_web_sm", True, "ok"

    def fake_get_engine():
        return object()

    def fast_anonymize(series, engine, entities, operator, threshold):
        return series, {}

    monkeypatch.setattr(pii_engine, "set_spacy_model", fake_set_spacy_model)
    monkeypatch.setattr(pii_engine, "get_engine", fake_get_engine)
    monkeypatch.setattr(tasks, "_anonymize_series", fast_anonymize)
    monkeypatch.setattr(tasks, "dd", None)

    _, stats = tasks.run_pii_anonymization(
        pd.DataFrame({"text": ["john@example.com"]}),
        {
            "job_id": "job-dask-fallback",
            "operator": "replace",
            "entities": ["EMAIL_ADDRESS"],
            "threshold": 0.35,
            "text_columns": ["text"],
            "chunk_size": 100,
            "compute_backend": "dask",
        },
    )

    assert stats["compute_backend_used"] == "pandas"
    assert "not installed" in str(stats["compute_backend_note"]).lower()


def test_run_task_uses_dask_partitions_when_available(monkeypatch):
    import pii_engine

    class _FakePartition:
        def __init__(self, part):
            self._part = part

        def compute(self, scheduler=None):
            return self._part

    class _FakeDaskFrame:
        def __init__(self, df, npartitions):
            step = max(1, (len(df) + npartitions - 1) // npartitions)
            self._parts = [df.iloc[i:i + step] for i in range(0, len(df), step)]
            self.npartitions = len(self._parts)

        def get_partition(self, idx):
            return _FakePartition(self._parts[idx])

    class _FakeDask:
        @staticmethod
        def from_pandas(df, npartitions):
            return _FakeDaskFrame(df, npartitions)

    def fake_set_spacy_model(choice):
        return "en_core_web_sm", True, "ok"

    def fake_get_engine():
        return object()

    def fast_anonymize(series, engine, entities, operator, threshold):
        out = series.str.replace("Alice", "[PERSON]", regex=False)
        return out, {"PERSON": int(series.notna().sum())}

    monkeypatch.setattr(pii_engine, "set_spacy_model", fake_set_spacy_model)
    monkeypatch.setattr(pii_engine, "get_engine", fake_get_engine)
    monkeypatch.setattr(tasks, "_anonymize_series", fast_anonymize)
    monkeypatch.setattr(tasks, "dd", _FakeDask)

    out, stats = tasks.run_pii_anonymization(
        pd.DataFrame({"text": ["Alice at Seattle clinic"] * 1200}),
        {
            "job_id": "job-dask-path",
            "operator": "replace",
            "entities": ["PERSON"],
            "threshold": 0.35,
            "text_columns": ["text"],
            "chunk_size": 200,
            "compute_backend": "dask",
        },
    )

    assert len(out) == 1200
    assert stats["compute_backend_used"] == "dask"
    assert stats["processed_rows"] == 1200


def test_run_task_reads_csv_path_with_dask_backend(monkeypatch, tmp_path):
    import pii_engine

    # Point the upload-dir guard at tmp_path so the path-traversal check passes.
    monkeypatch.setenv("ANON_UPLOAD_DIR", str(tmp_path))

    csv_path = tmp_path / "large_input.csv"
    pd.DataFrame({"text": ["Alice Seattle", "Alice Austin", "Alice Boston"]}).to_csv(csv_path, index=False)

    class _FakePartition:
        def __init__(self, part):
            self._part = part

        def compute(self, scheduler=None):
            return self._part

    class _FakeDaskFrame:
        def __init__(self, df, npartitions):
            step = max(1, (len(df) + npartitions - 1) // npartitions)
            self._parts = [df.iloc[i:i + step] for i in range(0, len(df), step)]
            self.npartitions = len(self._parts)

        def get_partition(self, idx):
            return _FakePartition(self._parts[idx])

    class _FakeDask:
        @staticmethod
        def read_csv(path, blocksize=None):
            return _FakeDaskFrame(pd.read_csv(path), npartitions=2)

        @staticmethod
        def from_pandas(df, npartitions):
            return _FakeDaskFrame(df, npartitions=npartitions)

    def fake_set_spacy_model(choice):
        return "en_core_web_sm", True, "ok"

    def fake_get_engine():
        return object()

    def fast_anonymize(series, engine, entities, operator, threshold):
        out = series.str.replace("Alice", "[PERSON]", regex=False)
        return out, {"PERSON": int(series.notna().sum())}

    monkeypatch.setattr(pii_engine, "set_spacy_model", fake_set_spacy_model)
    monkeypatch.setattr(pii_engine, "get_engine", fake_get_engine)
    monkeypatch.setattr(tasks, "_anonymize_series", fast_anonymize)
    monkeypatch.setattr(tasks, "dd", _FakeDask)

    out, stats = tasks.run_pii_anonymization(
        raw_df={},
        job_config={
            "job_id": "job-csv-path-dask",
            "operator": "replace",
            "entities": ["PERSON"],
            "threshold": 0.35,
            "text_columns": ["text"],
            "chunk_size": 2,
            "compute_backend": "dask",
            "input_csv_path": str(csv_path),
            "row_count_hint": 3,
        },
    )

    assert os.path.exists(csv_path)
    assert len(out) == 3
    assert stats["compute_backend_used"] == "dask"
    assert stats["processed_rows"] == 3
    assert "[PERSON]" in " ".join(out["text"].astype(str).tolist())


def test_run_task_accepts_default_upload_dir_without_env(monkeypatch, tmp_path):
    import pii_engine

    monkeypatch.delenv("ANON_UPLOAD_DIR", raising=False)

    upload_root = os.path.join(tempfile.gettempdir(), "anon_studio_uploads")
    os.makedirs(upload_root, exist_ok=True)
    csv_path = os.path.join(upload_root, "task_default_upload_guard.csv")
    pd.DataFrame({"text": ["Alice Seattle", "Alice Austin"]}).to_csv(csv_path, index=False)

    def fake_set_spacy_model(choice):
        return "en_core_web_sm", True, "ok"

    def fake_get_engine():
        return object()

    def fast_anonymize(series, engine, entities, operator, threshold):
        out = series.str.replace("Alice", "[PERSON]", regex=False)
        return out, {"PERSON": int(series.notna().sum())}

    monkeypatch.setattr(pii_engine, "set_spacy_model", fake_set_spacy_model)
    monkeypatch.setattr(pii_engine, "get_engine", fake_get_engine)
    monkeypatch.setattr(tasks, "_anonymize_series", fast_anonymize)
    monkeypatch.setattr(tasks, "dd", None)

    out, stats = tasks.run_pii_anonymization(
        raw_df={},
        job_config={
            "job_id": "job-default-upload-root",
            "operator": "replace",
            "entities": ["PERSON"],
            "threshold": 0.35,
            "text_columns": ["text"],
            "chunk_size": 100,
            "compute_backend": "pandas",
            "input_csv_path": csv_path,
            "row_count_hint": 2,
        },
    )

    assert len(out) == 2
    assert stats["processed_rows"] == 2
    assert not stats["errors"]
    os.remove(csv_path)
