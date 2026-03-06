"""
Tests for PIISession ↔ PipelineCard traceability.

Covers:
- Auto-attach: _load_job_results creates a PIISession and links it to the
  pipeline card when a file job completes.
- Manual attach: on_card_save attaches a session to a card and prevents
  duplicate attachments.
- Card history: on_card_history populates card_sessions_data with linked
  sessions.
- Audit trail: session.attach audit events are emitted on both auto and
  manual attach paths.

Run:
    pytest tests/test_session_card_traceability.py -v
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import app
from store.models import PIISession, PipelineCard


# ── Helpers ───────────────────────────────────────────────────────────────────

def _noop(*_args, **_kwargs):
    """No-op stub for monkeypatched functions."""


def _patch_common(monkeypatch):
    """Patch GUI helpers that are irrelevant to business-logic assertions."""
    monkeypatch.setattr(app, "notify", _noop)
    monkeypatch.setattr(app, "_refresh_pipeline", _noop)
    monkeypatch.setattr(app, "_refresh_audit", _noop)
    monkeypatch.setattr(app, "_refresh_dashboard", _noop)


# ── Auto-attach on file job completion ────────────────────────────────────────

class TestAutoAttachOnJobCompletion:
    """_load_job_results must create a PIISession linked to the card."""

    def test_session_created_and_linked_to_card(self, monkeypatch):
        _patch_common(monkeypatch)
        monkeypatch.setattr(app, "_refresh_job_errors", _noop)

        jid = "job-auto1"
        stats = {
            "entity_counts": {"PERSON": 3, "EMAIL_ADDRESS": 2},
            "duration_s": 1.5,
            "sample_before": ["Alice alice@test.com"],
        }
        config = {"file_name": "data.csv", "operator": "mask"}
        anon_df = pd.DataFrame([{"col": "<PERSON>"}])

        class _Node:
            def __init__(self, val):
                self._val = val
            def read(self):
                return self._val

        sc = SimpleNamespace(
            job_config=_Node(config),
            job_stats=_Node(stats),
            anon_output=_Node(anon_df),
        )
        app._SCENARIOS[jid] = sc

        card = PipelineCard(title="Upload", status="in_progress", job_id=jid)
        app.store.add_card(card)

        state = SimpleNamespace(
            stats_entity_rows=pd.DataFrame(),
            stats_entity_chart_figure={},
            job_quality_md="",
            preview_data=pd.DataFrame(),
            preview_cols=[],
            download_ready=False,
            download_scenario_id="",
            download_rows=0,
            download_cols=0,
        )

        app._load_job_results(state, jid)

        # Card should have moved to review
        updated_card = app.store.get_card(card.id)
        assert updated_card.status == "review"

        # A PIISession should be linked
        assert updated_card.session_id is not None
        session = app.store.get_session(updated_card.session_id)
        assert session is not None
        assert session.pipeline_card_id == card.id
        assert session.source_type == "file"
        assert session.operator == "mask"
        assert session.file_name == "data.csv"
        assert session.entity_counts == {"PERSON": 3, "EMAIL_ADDRESS": 2}
        assert session.processing_ms == 1500.0

        # session.attach audit entry should exist
        audit = app.store.list_audit(limit=100)
        attach_entries = [e for e in audit if e.action == "session.attach"
                          and e.resource_id == card.id]
        assert len(attach_entries) >= 1

        # Cleanup
        app._SCENARIOS.pop(jid, None)

    def test_only_in_progress_cards_get_session(self, monkeypatch):
        """Cards not in 'in_progress' status should be skipped."""
        _patch_common(monkeypatch)
        monkeypatch.setattr(app, "_refresh_job_errors", _noop)

        jid = "job-skip1"
        stats = {"entity_counts": {}, "duration_s": 0}
        anon_df = pd.DataFrame([{"x": 1}])

        class _Node:
            def __init__(self, val):
                self._val = val
            def read(self):
                return self._val

        sc = SimpleNamespace(
            job_config=_Node({}),
            job_stats=_Node(stats),
            anon_output=_Node(anon_df),
        )
        app._SCENARIOS[jid] = sc

        card_done = PipelineCard(title="Done card", status="done", job_id=jid)
        app.store.add_card(card_done)

        state = SimpleNamespace(
            stats_entity_rows=pd.DataFrame(),
            stats_entity_chart_figure={},
            job_quality_md="",
            preview_data=pd.DataFrame(),
            preview_cols=[],
            download_ready=False,
            download_scenario_id="",
            download_rows=0,
            download_cols=0,
        )

        app._load_job_results(state, jid)

        # Card should NOT have been updated (still "done")
        assert app.store.get_card(card_done.id).status == "done"
        assert app.store.get_card(card_done.id).session_id is None

        app._SCENARIOS.pop(jid, None)


# ── Manual attach via on_card_save ────────────────────────────────────────────

class TestManualSessionAttach:
    """on_card_save must attach sessions and prevent duplicates."""

    def test_session_attach_audit_on_new_card(self, monkeypatch):
        _patch_common(monkeypatch)
        captured_notify = []
        monkeypatch.setattr(app, "notify",
                            lambda _s, lvl, msg: captured_notify.append((lvl, msg)))

        session = PIISession(title="My Session", operator="replace")
        app.store.add_session(session)

        state = SimpleNamespace(
            card_id_edit="",
            card_title_f="New Card",
            card_desc_f="",
            card_status_f="backlog",
            card_assign_f="",
            card_priority_f="medium",
            card_labels_f="",
            card_attest_f="",
            card_session_f=f"{session.id[:8]} — My Session",
            card_form_open=True,
        )

        app.on_card_save(state)

        # Card should be created with session_id
        cards = app.store.list_cards()
        new_card = next((c for c in cards if c.title == "New Card"), None)
        assert new_card is not None
        assert new_card.session_id == session.id[:8]

        # session.attach audit entry
        audit = app.store.list_audit(limit=100)
        attach = [e for e in audit if e.action == "session.attach"
                  and e.resource_id == new_card.id]
        assert len(attach) >= 1

    def test_duplicate_session_attach_prevented(self, monkeypatch):
        _patch_common(monkeypatch)
        captured_notify = []
        monkeypatch.setattr(app, "notify",
                            lambda _s, lvl, msg: captured_notify.append((lvl, msg)))

        session = PIISession(title="Shared Session", operator="replace")
        app.store.add_session(session)

        # First card holds this session
        card1 = PipelineCard(title="Card 1", session_id=session.id[:8])
        app.store.add_card(card1)

        # Try to attach same session to a second card via edit
        card2 = PipelineCard(title="Card 2")
        app.store.add_card(card2)

        state = SimpleNamespace(
            card_id_edit=card2.id,
            card_title_f="Card 2",
            card_desc_f="",
            card_status_f="backlog",
            card_assign_f="",
            card_priority_f="medium",
            card_labels_f="",
            card_attest_f="",
            card_session_f=f"{session.id[:8]} — Shared Session",
            card_form_open=True,
        )

        app.on_card_save(state)

        # Warning should have been raised
        assert any(lvl == "warning" and "already attached" in msg
                   for lvl, msg in captured_notify)

    def test_no_session_attach_when_none_selected(self, monkeypatch):
        _patch_common(monkeypatch)
        monkeypatch.setattr(app, "notify", _noop)

        state = SimpleNamespace(
            card_id_edit="",
            card_title_f="Plain Card",
            card_desc_f="",
            card_status_f="backlog",
            card_assign_f="",
            card_priority_f="medium",
            card_labels_f="",
            card_attest_f="",
            card_session_f="(none)",
            card_form_open=True,
        )

        app.on_card_save(state)

        cards = app.store.list_cards()
        plain = next((c for c in cards if c.title == "Plain Card"), None)
        assert plain is not None
        assert plain.session_id is None

        # No session.attach audit entry for this card
        audit = app.store.list_audit(limit=100)
        attach = [e for e in audit if e.action == "session.attach"
                  and e.resource_id == plain.id]
        assert len(attach) == 0


# ── Card history dialog ───────────────────────────────────────────────────────

class TestCardHistoryDialog:
    """on_card_history must show linked sessions."""

    def test_card_history_shows_linked_sessions(self, monkeypatch):
        _patch_common(monkeypatch)

        card = PipelineCard(title="History Test")
        app.store.add_card(card)

        s1 = PIISession(title="Session A", operator="replace",
                        entity_counts={"PERSON": 2}, pipeline_card_id=card.id)
        s2 = PIISession(title="Session B", operator="mask",
                        entity_counts={"EMAIL_ADDRESS": 5}, pipeline_card_id=card.id)
        app.store.add_session(s1)
        app.store.add_session(s2)

        # Mock _get_selected_card_id to return our card
        monkeypatch.setattr(app, "_get_selected_card_id", lambda _state: card.id)

        state = SimpleNamespace(
            card_audit_data=pd.DataFrame(),
            card_sessions_data=pd.DataFrame(),
            card_audit_open=False,
        )

        app.on_card_history(state)

        assert state.card_audit_open is True
        assert len(state.card_sessions_data) == 2
        titles = list(state.card_sessions_data["Title"])
        assert any("Session A" in t for t in titles)
        assert any("Session B" in t for t in titles)

    def test_card_history_empty_sessions_shows_placeholder(self, monkeypatch):
        _patch_common(monkeypatch)

        card = PipelineCard(title="No Sessions")
        app.store.add_card(card)

        monkeypatch.setattr(app, "_get_selected_card_id", lambda _state: card.id)

        state = SimpleNamespace(
            card_audit_data=pd.DataFrame(),
            card_sessions_data=pd.DataFrame(),
            card_audit_open=False,
        )

        app.on_card_history(state)

        assert state.card_audit_open is True
        assert len(state.card_sessions_data) == 1
        assert state.card_sessions_data.iloc[0]["Title"] == "No sessions linked"

    def test_card_history_no_card_selected_warns(self, monkeypatch):
        _patch_common(monkeypatch)
        captured_notify = []
        monkeypatch.setattr(app, "notify",
                            lambda _s, lvl, msg: captured_notify.append((lvl, msg)))
        monkeypatch.setattr(app, "_get_selected_card_id", lambda _state: "")

        state = SimpleNamespace(
            card_audit_data=pd.DataFrame(),
            card_sessions_data=pd.DataFrame(),
            card_audit_open=False,
        )

        app.on_card_history(state)

        assert state.card_audit_open is False
        assert any(lvl == "warning" for lvl, _ in captured_notify)
