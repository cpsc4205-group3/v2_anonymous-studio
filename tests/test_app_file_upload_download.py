from __future__ import annotations

import io
import os
import tempfile
import warnings
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import app
from services.jobs import parse_upload_to_df


def test_parse_upload_to_df_csv_and_excel():
    src = pd.DataFrame(
        [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"},
        ]
    )

    csv_bytes = src.to_csv(index=False).encode("utf-8")
    csv_df = parse_upload_to_df(csv_bytes, "sample.csv")
    assert list(csv_df.columns) == ["name", "email"]
    assert len(csv_df) == 2

    xlsx_buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="openpyxl")
        src.to_excel(xlsx_buf, index=False)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="openpyxl")
        xlsx_df = parse_upload_to_df(xlsx_buf.getvalue(), "sample.xlsx")
    assert list(xlsx_df.columns) == ["name", "email"]
    assert len(xlsx_df) == 2


def test_on_file_upload_reads_temp_file_and_caches_bytes(monkeypatch, tmp_path):
    upload_root = Path(tempfile.gettempdir())
    upload_file = upload_root / "anon_upload_test.csv"
    upload_file.write_text("name,email\nAlice,alice@example.com\n", encoding="utf-8")

    state = SimpleNamespace(job_file_content=str(upload_file), job_file_name="")
    captured_notify = []
    monkeypatch.setattr(app, "get_state_id", lambda _state: "state-1")
    monkeypatch.setattr(app, "notify", lambda _state, level, msg: captured_notify.append((level, msg)))
    app._FILE_CACHE.clear()

    app.on_file_upload(state, action=None, payload={"name": "upload.csv"})

    assert state.job_file_name == "upload.csv"
    assert state.job_file_content == "upload.csv"
    assert "state-1" in app._FILE_CACHE
    assert app._FILE_CACHE["state-1"]["name"] == "upload.csv"
    assert isinstance(app._FILE_CACHE["state-1"]["bytes"], (bytes, bytearray))
    assert captured_notify and captured_notify[-1][0] == "success"


def test_on_download_exports_csv_and_cleans_job_registry(monkeypatch):
    anon_df = pd.DataFrame([{"id": 1, "value": "<EMAIL_ADDRESS>"}])

    class _Node:
        def read(self):
            return anon_df

    sc = SimpleNamespace(id="sc-1", anon_output=_Node())
    app._SCENARIOS["job-123"] = sc
    app._SUBMISSION_IDS["job-123"] = "sub-1"
    app.PROGRESS_REGISTRY["job-123"] = {"status": "done"}

    state = SimpleNamespace(download_scenario_id="job-123", active_job_id="")
    captured = {}
    monkeypatch.setattr(app, "download", lambda _state, content, name: captured.update({"content": content, "name": name}))
    monkeypatch.setattr(app, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_audit", lambda _state: None)
    monkeypatch.setattr(app, "delete_progress_snapshot", lambda _jid: None)
    monkeypatch.setattr(app.tc, "delete", lambda _sid: None)
    monkeypatch.setattr(app.store, "log_user_action", lambda *args, **kwargs: None)

    app.on_download(state)

    assert captured["name"] == "anonymized_job-123.csv"
    assert b"value" in captured["content"]
    assert b"<EMAIL_ADDRESS>" in captured["content"]
    assert "job-123" not in app._SCENARIOS
    assert "job-123" not in app._SUBMISSION_IDS
    assert "job-123" not in app.PROGRESS_REGISTRY


def test_build_geo_place_counts_maps_text_and_entities():
    sessions = [
        SimpleNamespace(
            original_text="Routing through Seattle and Austin, TX.",
            entities=[
                {"entity_type": "LOCATION", "text": "Seattle"},
                {"Entity Type": "GPE", "Text": "Austin TX"},
            ],
        )
    ]

    counts, unmapped = app._build_geo_place_counts(sessions, app.GEO_CITY_COORDS)

    assert counts.get("seattle", 0) >= 1
    assert counts.get("austin", 0) >= 1
    assert unmapped == 0


def test_build_geo_place_counts_tracks_unmapped_location_mentions():
    sessions = [
        SimpleNamespace(
            original_text="",
            entities=[{"entity_type": "LOCATION", "text": "Springfield"}],
        )
    ]

    counts, unmapped = app._build_geo_place_counts(sessions, app.GEO_CITY_COORDS)

    assert counts == {}
    assert unmapped == 1


def test_on_submit_job_csv_uses_staged_path_payload(monkeypatch, tmp_path):
    csv_bytes = b"text\nAlice Seattle\nAlice Austin\n"
    state = SimpleNamespace(
        job_file_content="upload.csv",
        job_file_name="upload.csv",
        job_operator="replace",
        job_entities=["PERSON"],
        job_threshold=0.35,
        job_chunk_size=500,
        job_spacy_model="auto",
        job_card_id="",
        job_quality_md="",
        active_job_id="",
        job_is_running=False,
        job_active_submission_id="",
        job_submission_status="",
        job_progress_pct=0.0,
        job_progress_msg="",
        job_progress_status="",
        job_expected_rows=0,
        job_active_started=0.0,
        job_view_tab="Results",
    )

    captured = {}
    monkeypatch.setattr(app, "get_state_id", lambda _state: "state-csv")
    monkeypatch.setattr(app, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_persist_progress", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(app, "_refresh_job_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.store, "log_user_action", lambda *_args, **_kwargs: None)

    def fake_invoke_long_callback(_state, user_function, user_function_args, user_status_function, period):
        captured["args"] = user_function_args
        captured["period"] = period

    monkeypatch.setattr(app, "invoke_long_callback", fake_invoke_long_callback)
    monkeypatch.setattr(app, "new_job_id", lambda: "jobcsv123456")

    app._FILE_CACHE["state-csv"] = {"bytes": csv_bytes, "name": "upload.csv"}

    app.on_submit_job(state)

    assert "args" in captured
    raw_payload, config = captured["args"]
    assert isinstance(raw_payload, dict)
    assert raw_payload.get("source") == "csv_path"
    assert str(config.get("input_csv_path", "")).endswith("_upload.csv")
    assert int(config.get("row_count_hint", 0)) >= 2
    assert os.path.exists(config["input_csv_path"])
    os.remove(config["input_csv_path"])


def test_sync_active_job_progress_keeps_error_when_taipy_reports_done(monkeypatch):
    state = SimpleNamespace(
        active_job_id="job-err-1",
        job_expected_rows=10,
        job_progress_pct=0.0,
        job_progress_msg="",
        job_progress_status="running",
        job_is_running=False,
    )

    app._SCENARIOS["job-err-1"] = SimpleNamespace(id="sc-err-1")
    monkeypatch.setattr(
        app,
        "_progress_from_sources",
        lambda _jid: {
            "pct": 100.0,
            "processed": 0,
            "total": 10,
            "message": "Rejected: CSV path is outside the allowed upload directory.",
            "status": "error",
        },
    )
    monkeypatch.setattr(app, "_resolve_job_status", lambda _scenario_id: "done")
    monkeypatch.setattr(app, "_persist_progress", lambda _jid, payload: payload)
    monkeypatch.setattr(app, "_refresh_job_health", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_job_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_dashboard", lambda *_args, **_kwargs: None)

    changed = app._sync_active_job_progress(state, load_results_on_done=False)

    assert changed is True
    assert state.job_progress_status == "error"
    assert "Rejected:" in state.job_progress_msg
    app._SCENARIOS.pop("job-err-1", None)


def test_refresh_job_health_marks_submission_failed_for_error_progress(monkeypatch):
    state = SimpleNamespace(
        active_job_id="job-err-2",
        job_progress_pct=0.0,
        job_progress_msg="",
        job_progress_status="error",
        job_is_running=False,
        job_expected_rows=0,
        job_active_started=0.0,
    )

    monkeypatch.setattr(
        app,
        "_progress_from_sources",
        lambda _jid: {"pct": 100, "processed": 0, "total": 0, "status": "error", "message": "Rejected: test"},
    )
    monkeypatch.setattr(app, "_resolve_submission_state", lambda _jid: {"id": "sub-1", "status": "Completed"})

    app._refresh_job_health(state)

    assert state.job_run_health == "Error"
    assert state.job_submission_status == "Failed"
    assert state.job_eta_text == "ETA unavailable"


def test_on_dash_seed_demo_creates_session(monkeypatch):
    state = SimpleNamespace(
        qt_entities=["PERSON"],
        qt_operator="replace",
        qt_threshold=0.35,
    )
    captured_notify = []
    captured = {}
    demo_entities = [
        {
            "entity_type": "PERSON",
            "text": "Jane Doe",
            "score": 0.99,
            "start": 9,
            "end": 17,
            "recognizer": "test",
        }
    ]
    demo_result = SimpleNamespace(anonymized_text="Patient: <PERSON>", entities=demo_entities)

    monkeypatch.setattr(app.engine, "anonymize", lambda *_args, **_kwargs: demo_result)
    monkeypatch.setattr(app.store, "add_session", lambda session: captured.setdefault("session", session))
    monkeypatch.setattr(app.store, "log_user_action", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_sessions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_dashboard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_ui_demo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_plotly_playground", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "notify", lambda _state, level, msg: captured_notify.append((level, msg)))

    app.on_dash_seed_demo(state)

    assert state.qt_session_saved is True
    assert "session" in captured
    assert captured["session"].title == "Demo medical record"
    assert not state.qt_entity_rows.empty
    assert captured_notify and captured_notify[-1][0] == "success"


def test_on_dash_seed_demo_falls_back_when_anonymize_fails(monkeypatch):
    state = SimpleNamespace(
        qt_entities=app.ALL_ENTITIES.copy(),
        qt_operator="replace",
        qt_threshold=0.35,
    )
    captured_notify = []
    captured = {}

    def _raise(*_args, **_kwargs):
        raise RuntimeError("anonymize failed")

    monkeypatch.setattr(app.engine, "anonymize", _raise)
    monkeypatch.setattr(app.store, "add_session", lambda session: captured.setdefault("session", session))
    monkeypatch.setattr(app.store, "log_user_action", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_sessions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_dashboard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_ui_demo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_plotly_playground", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "notify", lambda _state, level, msg: captured_notify.append((level, msg)))

    app.on_dash_seed_demo(state)

    assert state.qt_session_saved is True
    assert "session" in captured
    assert captured["session"].entity_counts.get("LOCATION", 0) >= 1
    assert "<LOCATION>" in state.qt_anonymized_raw
    assert captured_notify and captured_notify[-1][0] == "warning"


def test_on_dash_seed_demo_notifies_when_store_save_fails(monkeypatch):
    state = SimpleNamespace(
        qt_entities=["PERSON"],
        qt_operator="replace",
        qt_threshold=0.35,
    )
    captured_notify = []

    demo_entities = [
        {
            "entity_type": "PERSON",
            "text": "Jane Doe",
            "score": 0.99,
            "start": 9,
            "end": 17,
            "recognizer": "test",
        }
    ]
    demo_result = SimpleNamespace(anonymized_text="Patient: <PERSON>", entities=demo_entities)

    monkeypatch.setattr(app.engine, "anonymize", lambda *_args, **_kwargs: demo_result)
    monkeypatch.setattr(app.store, "add_session", lambda _session: (_ for _ in ()).throw(RuntimeError("store down")))
    monkeypatch.setattr(app.store, "log_user_action", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_sessions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_dashboard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_ui_demo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_plotly_playground", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_refresh_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "notify", lambda _state, level, msg: captured_notify.append((level, msg)))

    app.on_dash_seed_demo(state)

    assert state.qt_session_saved is False
    assert captured_notify and captured_notify[-1][0] == "error"


# ── _playground_store_data tests ──────────────────────────────────────────────

def test_playground_store_data_returns_none_when_empty(monkeypatch):
    """With no sessions, _playground_store_data returns None (sample fallback)."""
    monkeypatch.setattr(
        app.store, "stats",
        lambda: {"entity_breakdown": {}, "pipeline_by_status": {}},
    )
    monkeypatch.setattr(app.store, "list_sessions", lambda: [])
    assert app._playground_store_data() is None


def test_playground_store_data_returns_real_data(monkeypatch):
    """With sessions in the store, _playground_store_data returns chart-ready data."""
    from store.models import PIISession

    sess = PIISession(
        title="Test",
        entities=[
            {"Entity Type": "PERSON", "Confidence": 92, "Recognizer": "SpacyRecognizer", "Text": "Jane"},
            {"Entity Type": "EMAIL_ADDRESS", "Confidence": 88, "Recognizer": "PatternRecognizer", "Text": "j@x.co"},
        ],
        entity_counts={"PERSON": 1, "EMAIL_ADDRESS": 1},
        processing_ms=42.5,
    )
    monkeypatch.setattr(
        app.store, "stats",
        lambda: {
            "entity_breakdown": {"PERSON": 3, "EMAIL_ADDRESS": 2},
            "pipeline_by_status": {"backlog": 1, "done": 2},
        },
    )
    monkeypatch.setattr(app.store, "list_sessions", lambda: [sess])

    sd = app._playground_store_data()

    assert sd is not None
    assert sd["labels"] == ["PERSON", "EMAIL_ADDRESS"]
    assert sd["counts"] == [3, 2]
    assert "PERSON" in sd["conf_by_type"]
    assert 92 in sd["conf_by_type"]["PERSON"]
    assert 88 in sd["all_confs"]
    assert sd["funnel_counts"][0] == 1   # backlog
    assert sd["funnel_counts"][3] == 2   # done
    assert "SpacyRecognizer" in sd["recog_entity"]
