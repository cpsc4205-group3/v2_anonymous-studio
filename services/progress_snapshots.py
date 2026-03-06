"""Durable job progress snapshots shared between GUI and worker processes."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from datetime import datetime
from typing import Any, Dict


_DEFAULT_ROOT = os.path.join(tempfile.gettempdir(), "anon_studio")
_SNAPSHOT_DIR = os.path.join(
    os.environ.get("ANON_STORAGE", _DEFAULT_ROOT),
    "progress_snapshots",
)


def _safe_job_id(job_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(job_id or "").strip()) or "unknown"


def _snapshot_path(job_id: str) -> str:
    return os.path.join(_SNAPSHOT_DIR, f"{_safe_job_id(job_id)}.json")


def _normalized_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    pct = float(payload.get("pct", 0) or 0)
    pct = min(max(pct, 0.0), 100.0)
    processed = int(payload.get("processed", 0) or 0)
    total = int(payload.get("total", 0) or 0)
    updated_at = float(payload.get("updated_at", 0) or 0.0) or time.time()
    return {
        "pct": round(pct, 1),
        "processed": max(0, processed),
        "total": max(0, total),
        "message": str(payload.get("message", "") or ""),
        "status": str(payload.get("status", "") or "").lower(),
        "ts": str(payload.get("ts", "") or datetime.now().isoformat(timespec="seconds")),
        "updated_at": updated_at,
    }


def write_progress_snapshot(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not job_id:
        return {}
    data = _normalized_payload(payload)
    os.makedirs(_SNAPSHOT_DIR, mode=0o700, exist_ok=True)
    path = _snapshot_path(job_id)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True)
    os.replace(tmp, path)
    return data


def read_progress_snapshot(job_id: str) -> Dict[str, Any]:
    if not job_id:
        return {}
    path = _snapshot_path(job_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return _normalized_payload(data)
    except Exception:
        return {}


def delete_progress_snapshot(job_id: str) -> None:
    if not job_id:
        return
    try:
        os.remove(_snapshot_path(job_id))
    except FileNotFoundError:
        return
    except Exception:
        return
