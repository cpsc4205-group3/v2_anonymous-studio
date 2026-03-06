from __future__ import annotations

from services import progress_snapshots as ps


def test_write_and_read_snapshot_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(ps, "_SNAPSHOT_DIR", str(tmp_path))
    payload = {
        "pct": 42.345,
        "processed": 21,
        "total": 50,
        "message": "Chunk 2/5",
        "status": "running",
    }
    written = ps.write_progress_snapshot("job-123", payload)
    loaded = ps.read_progress_snapshot("job-123")

    assert written["pct"] == 42.3
    assert loaded["processed"] == 21
    assert loaded["total"] == 50
    assert loaded["status"] == "running"
    assert loaded["message"] == "Chunk 2/5"
    assert loaded["updated_at"] > 0


def test_delete_snapshot_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(ps, "_SNAPSHOT_DIR", str(tmp_path))
    ps.write_progress_snapshot("job-delete", {"pct": 100, "status": "done"})

    ps.delete_progress_snapshot("job-delete")
    ps.delete_progress_snapshot("job-delete")

    assert ps.read_progress_snapshot("job-delete") == {}
