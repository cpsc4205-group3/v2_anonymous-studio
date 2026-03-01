"""
Anonymous Studio — Task Functions
The actual computation that runs inside taipy.core jobs.

run_pii_anonymization(raw_df, job_config) → (anonymized_df, job_stats)

Features:
  • Auto-detects text columns with PII patterns
  • Chunked row processing — memory-safe for large files
  • Per-chunk progress written to PROGRESS_REGISTRY (polled by GUI)
  • Per-column entity counts and timing
  • Error isolation — bad rows never kill the whole job
"""
from __future__ import annotations
import re, time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd

# ── Shared progress registry ──────────────────────────────────────────────────
# job_id → { pct, processed, total, message, status }
# Written inside the task thread, read by the GUI polling loop.
PROGRESS_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _progress(job_id: str, pct: float, processed: int,
              total: int, msg: str, status: str = "running"):
    PROGRESS_REGISTRY[job_id] = {
        "pct":       round(min(pct, 100.0), 1),
        "processed": processed,
        "total":     total,
        "message":   msg,
        "status":    status,          # running | done | error
        "ts":        datetime.now().isoformat(timespec="seconds"),
    }


# ── Main task ─────────────────────────────────────────────────────────────────
def run_pii_anonymization(
    raw_df:     pd.DataFrame,
    job_config: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    taipy.core Task — called by the Orchestrator in a background thread.

    Inputs  (DataNodes):  raw_df, job_config
    Outputs (DataNodes):  anonymized_df, job_stats
    """
    from pii_engine import get_engine, ALL_ENTITIES

    job_id     = job_config.get("job_id", "unknown")
    operator   = job_config.get("operator", "replace")
    entities   = job_config.get("entities", ALL_ENTITIES)
    threshold  = job_config.get("threshold", 0.35)
    text_cols  = job_config.get("text_columns", [])   # [] = auto-detect
    chunk_size = job_config.get("chunk_size", 500)

    t0         = datetime.now()
    engine     = get_engine()
    total_rows = len(raw_df)

    stats: Dict[str, Any] = {
        "job_id":          job_id,
        "total_rows":      total_rows,
        "processed_rows":  0,
        "total_entities":  0,
        "entity_counts":   {},
        "cols_processed":  [],
        "operator":        operator,
        "started_at":      t0.isoformat(),
        "finished_at":     None,
        "duration_s":      None,
        "errors":          [],
        "sample_before":   [],
        "sample_after":    [],
    }

    _progress(job_id, 0, 0, total_rows, "Initializing engine…")

    # ── Edge cases ────────────────────────────────────────────────────────────
    if raw_df is None or raw_df.empty:
        _progress(job_id, 100, 0, 0, "Empty dataset — nothing to do.", "done")
        stats["finished_at"] = datetime.now().isoformat()
        stats["duration_s"]  = 0
        return pd.DataFrame(), stats

    # ── Column detection ──────────────────────────────────────────────────────
    if not text_cols:
        text_cols = _detect_text_columns(raw_df)

    if not text_cols:
        msg = "No text columns detected. Check your file or specify columns manually."
        _progress(job_id, 100, total_rows, total_rows, msg, "error")
        stats["errors"].append(msg)
        stats["finished_at"] = datetime.now().isoformat()
        return raw_df.copy(), stats

    stats["cols_processed"] = text_cols
    stats["sample_before"]  = raw_df[text_cols].head(3).fillna("").to_dict("records")

    # ── Chunked processing ────────────────────────────────────────────────────
    output     = raw_df.copy()
    processed  = 0
    all_counts: Dict[str, int] = {}
    n_chunks   = max(1, (total_rows + chunk_size - 1) // chunk_size)

    for chunk_idx, (start, chunk) in enumerate(_chunks(raw_df, chunk_size)):
        _progress(
            job_id,
            pct       = processed / total_rows * 94,
            processed = processed,
            total     = total_rows,
            msg       = f"Chunk {chunk_idx + 1}/{n_chunks} "
                        f"· rows {start}–{start + len(chunk) - 1}",
        )

        for col in text_cols:
            if col not in chunk.columns:
                continue
            try:
                anon_series, counts = _anonymize_series(
                    chunk[col], engine, entities, operator, threshold
                )
                col_idx = output.columns.get_loc(col)
                output.iloc[start : start + len(chunk), col_idx] = anon_series.values

                for etype, cnt in counts.items():
                    all_counts[etype] = all_counts.get(etype, 0) + cnt

            except Exception as exc:
                err = f"Chunk {chunk_idx} · col '{col}': {exc}"
                stats["errors"].append(err)

        processed += len(chunk)

    # ── Finalise stats ────────────────────────────────────────────────────────
    t1 = datetime.now()
    stats["processed_rows"]  = processed
    stats["entity_counts"]   = all_counts
    stats["total_entities"]  = sum(all_counts.values())
    stats["sample_after"]    = output[text_cols].head(3).fillna("").to_dict("records")
    stats["finished_at"]     = t1.isoformat()
    stats["duration_s"]      = round((t1 - t0).total_seconds(), 2)

    _progress(
        job_id, 100, total_rows, total_rows,
        f"✅ {stats['total_entities']} entities anonymized "
        f"across {len(text_cols)} column(s) in {stats['duration_s']}s",
        "done",
    )
    return output, stats


# ── Helpers ───────────────────────────────────────────────────────────────────

_PII_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"   # email
    r"|\b\d{3}[-.\s]\d{2}[-.\s]\d{4}\b"                   # SSN
    r"|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"                   # phone
    r"|\b(?:\d[ -]?){13,16}\b",                             # credit card
    re.I,
)


def _detect_text_columns(df: pd.DataFrame, sample: int = 100) -> List[str]:
    """Return columns that likely contain free text or PII values."""
    cols = []
    for col in df.columns:
        if df[col].dtype != object:
            continue
        s = df[col].dropna().head(sample).astype(str)
        if s.empty:
            continue
        avg_words = s.str.split().str.len().mean()
        pii_hits  = s.str.contains(_PII_RE).sum()
        if avg_words >= 1.5 or pii_hits > 0:
            cols.append(col)
    # Fallback: all string columns (capped at 8)
    if not cols:
        cols = [c for c in df.columns if df[c].dtype == object][:8]
    return cols


def _chunks(df: pd.DataFrame, size: int):
    for start in range(0, len(df), size):
        yield start, df.iloc[start : start + size]


def _anonymize_series(
    series: pd.Series,
    engine,
    entities: List[str],
    operator: str,
    threshold: float,
) -> Tuple[pd.Series, Dict[str, int]]:
    counts: Dict[str, int] = {}
    out = []
    for cell in series:
        if pd.isna(cell) or str(cell).strip() == "":
            out.append(cell)
            continue
        result = engine.anonymize(
            text=str(cell), entities=entities,
            operator=operator, threshold=threshold,
        )
        out.append(result.anonymized_text)
        for etype, cnt in result.entity_counts.items():
            counts[etype] = counts.get(etype, 0) + cnt
    return pd.Series(out, index=series.index), counts