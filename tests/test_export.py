"""
Tests for card-011: Export Audit Logs and Pipeline Cards (CSV/JSON).

Run:
    pytest tests/test_export.py -v

Covers:
- on_audit_export_csv  — exports audit entries as CSV bytes
- on_audit_export_json — exports audit entries as JSON bytes
- on_pipeline_export_csv  — exports pipeline cards as CSV bytes
- on_pipeline_export_json — exports pipeline cards as JSON bytes
- Each export logs an audit trail entry
- Exports contain correct data for all rows
"""
from __future__ import annotations

import io
import json
import dataclasses
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ModuleNotFoundError:
    _PANDAS_AVAILABLE = False

from store.memory import MemoryStore
from store.models import PipelineCard


# ── helpers ────────────────────────────────────────────────────────────────

def _make_store_with_data():
    """Return a MemoryStore pre-populated with audit entries and pipeline cards."""
    s = MemoryStore(seed=False)
    s.log_user_action("user", "test.action", "session", "s1", "first entry", severity="info")
    s.log_user_action("admin", "test.delete", "card", "c1", "second entry", severity="warning")

    card1 = PipelineCard(title="Card A", status="backlog", priority="high", assignee="alice")
    card2 = PipelineCard(title="Card B", status="done", priority="low", assignee="bob", attested=True)
    s.add_card(card1)
    s.add_card(card2)
    return s, card1, card2


def _run_export_callback(callback_name: str, store_instance: MemoryStore):
    """Invoke an export callback with a mock Taipy state and return the download call args."""
    try:
        import app as app_module
    except ModuleNotFoundError as exc:
        pytest.skip(f"app or dependency not importable in this environment: {exc}")

    downloaded = {}

    def fake_download(state, content, name):
        downloaded["content"] = content
        downloaded["name"] = name

    def fake_notify(state, level, msg):
        downloaded["notify_level"] = level

    mock_state = MagicMock()

    with patch.object(app_module, "store", store_instance), \
         patch.object(app_module, "download", side_effect=fake_download), \
         patch.object(app_module, "notify", side_effect=fake_notify):
        getattr(app_module, callback_name)(mock_state)

    return downloaded


# ── audit CSV export ────────────────────────────────────────────────────────

class TestAuditExportCsv:
    def test_returns_csv_bytes(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_csv", s)
        assert result["name"] == "audit_log.csv"
        content = result["content"]
        assert isinstance(content, bytes)
        df = pd.read_csv(io.BytesIO(content))
        assert "timestamp" in df.columns
        assert "actor" in df.columns
        assert "action" in df.columns
        assert "severity" in df.columns

    def test_csv_contains_all_entries(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_csv", s)
        df = pd.read_csv(io.BytesIO(result["content"]))
        # At least 2 user-added entries
        assert len(df) >= 2

    def test_success_notification(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_csv", s)
        assert result["notify_level"] == "success"

    def test_export_logged_to_audit(self):
        s, _, _ = _make_store_with_data()
        count_before = len(s.list_audit(limit=500))
        _run_export_callback("on_audit_export_csv", s)
        entries = s.list_audit(limit=500)
        assert len(entries) == count_before + 1
        assert entries[0].action == "audit.export_csv"


# ── audit JSON export ───────────────────────────────────────────────────────

class TestAuditExportJson:
    def test_returns_json_bytes(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_json", s)
        assert result["name"] == "audit_log.json"
        data = json.loads(result["content"].decode("utf-8"))
        assert isinstance(data, list)

    def test_json_contains_all_entries(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_json", s)
        data = json.loads(result["content"].decode("utf-8"))
        assert len(data) >= 2

    def test_json_fields(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_json", s)
        data = json.loads(result["content"].decode("utf-8"))
        first = data[0]
        for field in ("timestamp", "actor", "action", "resource_type", "details", "severity"):
            assert field in first, f"Missing field: {field}"

    def test_success_notification(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_audit_export_json", s)
        assert result["notify_level"] == "success"

    def test_export_logged_to_audit(self):
        s, _, _ = _make_store_with_data()
        count_before = len(s.list_audit(limit=500))
        _run_export_callback("on_audit_export_json", s)
        entries = s.list_audit(limit=500)
        assert len(entries) == count_before + 1
        assert entries[0].action == "audit.export_json"


# ── pipeline CSV export ─────────────────────────────────────────────────────

class TestPipelineExportCsv:
    def test_returns_csv_bytes(self):
        s, card1, card2 = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_csv", s)
        assert result["name"] == "pipeline_cards.csv"
        content = result["content"]
        assert isinstance(content, bytes)
        df = pd.read_csv(io.BytesIO(content))
        assert "id" in df.columns
        assert "title" in df.columns
        assert "status" in df.columns

    def test_csv_contains_all_cards(self):
        s, card1, card2 = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_csv", s)
        df = pd.read_csv(io.BytesIO(result["content"]))
        assert len(df) == 2
        titles = set(df["title"].tolist())
        assert "Card A" in titles
        assert "Card B" in titles

    def test_success_notification(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_csv", s)
        assert result["notify_level"] == "success"

    def test_export_logged_to_audit(self):
        s, _, _ = _make_store_with_data()
        _run_export_callback("on_pipeline_export_csv", s)
        entries = s.list_audit(limit=500)
        actions = [e.action for e in entries]
        assert "pipeline.export_csv" in actions


# ── pipeline JSON export ────────────────────────────────────────────────────

class TestPipelineExportJson:
    def test_returns_json_bytes(self):
        s, card1, card2 = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_json", s)
        assert result["name"] == "pipeline_cards.json"
        data = json.loads(result["content"].decode("utf-8"))
        assert isinstance(data, list)

    def test_json_contains_all_cards(self):
        s, card1, card2 = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_json", s)
        data = json.loads(result["content"].decode("utf-8"))
        assert len(data) == 2
        titles = {d["title"] for d in data}
        assert "Card A" in titles
        assert "Card B" in titles

    def test_json_fields(self):
        s, card1, _ = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_json", s)
        data = json.loads(result["content"].decode("utf-8"))
        first = next(d for d in data if d["title"] == "Card A")
        for field in ("id", "title", "status", "priority", "assignee", "attested", "created_at"):
            assert field in first, f"Missing field: {field}"

    def test_success_notification(self):
        s, _, _ = _make_store_with_data()
        result = _run_export_callback("on_pipeline_export_json", s)
        assert result["notify_level"] == "success"

    def test_export_logged_to_audit(self):
        s, _, _ = _make_store_with_data()
        _run_export_callback("on_pipeline_export_json", s)
        entries = s.list_audit(limit=500)
        actions = [e.action for e in entries]
        assert "pipeline.export_json" in actions


# ── serialization unit tests (no app import needed) ────────────────────────

class TestExportSerializationLogic:
    """Pure-logic tests that verify serialization without importing app."""

    def test_audit_entries_csv_format(self):
        if not _PANDAS_AVAILABLE:
            pytest.skip("pandas not available")
        s, _, _ = _make_store_with_data()
        entries = s.list_audit(limit=500)
        df = pd.DataFrame([
            {
                "timestamp": e.timestamp,
                "actor": e.actor,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "severity": e.severity,
            }
            for e in entries
        ])
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        assert isinstance(csv_bytes, bytes)
        roundtrip = pd.read_csv(io.BytesIO(csv_bytes))
        assert len(roundtrip) == len(entries)

    def test_audit_entries_json_format(self):
        s, _, _ = _make_store_with_data()
        entries = s.list_audit(limit=500)
        data = [
            {
                "timestamp": e.timestamp,
                "actor": e.actor,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "severity": e.severity,
            }
            for e in entries
        ]
        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        roundtrip = json.loads(json_bytes.decode("utf-8"))
        assert len(roundtrip) == len(entries)

    def test_pipeline_cards_csv_format(self):
        if not _PANDAS_AVAILABLE:
            pytest.skip("pandas not available")
        s, _, _ = _make_store_with_data()
        cards = s.list_cards()
        df = pd.DataFrame([
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "priority": c.priority,
                "assignee": c.assignee,
                "labels": ";".join(c.labels),
                "attested": c.attested,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in cards
        ])
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        roundtrip = pd.read_csv(io.BytesIO(csv_bytes))
        assert len(roundtrip) == 2

    def test_pipeline_cards_json_format(self):
        s, _, _ = _make_store_with_data()
        cards = s.list_cards()
        data = [dataclasses.asdict(c) for c in cards]
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        roundtrip = json.loads(json_bytes.decode("utf-8"))
        assert len(roundtrip) == 2
        assert all("title" in d for d in roundtrip)
