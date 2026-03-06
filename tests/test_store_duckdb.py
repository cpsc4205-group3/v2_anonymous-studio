from __future__ import annotations

import os

import pytest

from store import PipelineCard, get_store, _reset_store

duckdb = pytest.importorskip("duckdb")
assert duckdb is not None

from store.duckdb import DuckDBStore  # noqa: E402


def test_duckdb_store_card_roundtrip(tmp_path):
    db_path = tmp_path / "anon.duckdb"
    s = DuckDBStore(path=str(db_path), seed=False)
    card = PipelineCard(title="Duck card", status="backlog")
    s.add_card(card)
    got = s.get_card(card.id)
    assert got is not None
    assert got.title == "Duck card"
    assert s.stats()["pipeline_by_status"]["backlog"] == 1


def test_duckdb_update_card_to_done_sets_done_at(tmp_path):
    db_path = tmp_path / "done.duckdb"
    s = DuckDBStore(path=str(db_path), seed=False)
    card = PipelineCard(title="Finish me", status="review")
    s.add_card(card)
    updated = s.update_card(card.id, status="done")
    assert updated.done_at is not None


def test_duckdb_update_card_reopen_clears_done_at(tmp_path):
    db_path = tmp_path / "reopen.duckdb"
    s = DuckDBStore(path=str(db_path), seed=False)
    card = PipelineCard(title="Reopen me", status="backlog")
    s.add_card(card)
    s.update_card(card.id, status="done")
    reopened = s.update_card(card.id, status="review")
    assert reopened.done_at is None


def test_factory_returns_duckdb_store(tmp_path):
    db_path = tmp_path / "factory.duckdb"
    _reset_store()
    os.environ["ANON_STORE_BACKEND"] = "duckdb"
    os.environ["ANON_DUCKDB_PATH"] = str(db_path)
    try:
        s = get_store()
        assert isinstance(s, DuckDBStore)
    finally:
        _reset_store()
        os.environ.pop("ANON_STORE_BACKEND", None)
        os.environ.pop("ANON_DUCKDB_PATH", None)
