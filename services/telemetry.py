"""
Anonymous Studio — Taipy Telemetry (Prometheus exporter)

Hooks into the Taipy EventProcessor to emit Prometheus metrics for every
job lifecycle change.  A lightweight HTTP server (started via
`start_metrics_server`) lets Prometheus scrape those metrics at
``http://<host>:<ANON_METRICS_PORT>/metrics``.

Grafana (or any Prometheus-compatible tool) can then visualise:
  - Functional metric : jobs created / completed / failed  (Counter)
  - Operational metric: job queue depth per status          (Gauge)
  - Performance metric: job execution duration              (Histogram)
  - Data metric       : entities detected / rows processed  (Counter)

Environment variables
---------------------
ANON_METRICS_PORT  Port for the Prometheus metrics endpoint.
                   Set to a positive integer to enable  (e.g. 9100).
                   Defaults to 0 (disabled).

Usage (called from app.py once the EventProcessor is live)
----------------------------------------------------------
    from services.telemetry import register_telemetry, start_metrics_server

    register_telemetry(event_processor)   # subscribe to Taipy events
    start_metrics_server(9100)            # expose /metrics

Public API
----------
    register_telemetry(event_processor)  -> None
    start_metrics_server(port)           -> None
    record_job_completion(job_id, stats) -> None   # called from tasks.py / bg thread
"""
from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)

# ── Optional Prometheus dependency ─────────────────────────────────────────────
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        start_http_server as _prom_start_http_server,
    )
    _PROM_AVAILABLE = True
except ImportError:  # prometheus_client not installed
    _PROM_AVAILABLE = False
    _log.warning(
        "[Telemetry] prometheus_client is not installed.  "
        "Metrics collection is disabled.  "
        "Install with: pip install prometheus_client"
    )

# ── Metric definitions (created only when prometheus_client is available) ──────
if _PROM_AVAILABLE:
    _JOBS_CREATED = Counter(
        "anon_jobs_created_total",
        "Total number of Taipy jobs created (submitted to the Orchestrator).",
    )
    _JOBS_STATUS = Counter(
        "anon_jobs_status_total",
        "Total number of Taipy jobs that reached a terminal or transitional status.",
        ["status"],          # COMPLETED | FAILED | CANCELED | RUNNING | SKIPPED …
    )
    _SCENARIOS_CREATED = Counter(
        "anon_scenarios_created_total",
        "Total number of PII pipeline scenarios created.",
    )
    _JOB_DURATION = Histogram(
        "anon_job_duration_seconds",
        "Wall-clock duration of completed or failed PII pipeline jobs.",
        buckets=(5, 15, 30, 60, 120, 300, 600, float("inf")),
    )
    _ENTITIES_DETECTED = Counter(
        "anon_entities_detected_total",
        "Cumulative PII entities detected across all completed jobs.",
    )
    _ROWS_PROCESSED = Counter(
        "anon_rows_processed_total",
        "Cumulative dataset rows processed across all completed jobs.",
    )
    _QUEUE_DEPTH = Gauge(
        "anon_job_queue_depth",
        "Current number of Taipy jobs in a given status.",
        ["status"],
    )

# ── Per-job start-time registry (for duration calculation) ──────────────────────
_job_start: Dict[str, float] = {}
_job_start_lock = Lock()

# ── Guard: only register once ──────────────────────────────────────────────────
_registered = False


def _on_telemetry_event(event: Any) -> None:
    """Server-side Taipy event callback (no GUI state)."""
    if not _PROM_AVAILABLE:
        return
    try:
        entity_type = str(getattr(event, "entity_type", ""))
        operation   = str(getattr(event, "operation",   ""))
        attr_name   = str(getattr(event, "attribute_name",  "") or "")
        attr_value  = str(getattr(event, "attribute_value", "") or "")
        entity_id   = str(getattr(event, "entity_id",   "") or "")

        # ── Job created ───────────────────────────────────────────────────────
        if "JOB" in entity_type and "CREATION" in operation:
            _JOBS_CREATED.inc()
            with _job_start_lock:
                _job_start[entity_id] = time.monotonic()
            return

        # ── Job status update ─────────────────────────────────────────────────
        if "JOB" in entity_type and "UPDATE" in operation and attr_name == "status":
            status_upper = attr_value.upper()
            _JOBS_STATUS.labels(status=status_upper).inc()
            _QUEUE_DEPTH.labels(status=status_upper).inc()

            terminal = {"COMPLETED", "FAILED", "CANCELED", "SKIPPED", "ABANDONED"}
            if any(t in status_upper for t in terminal):
                # Decrement queue depth for running/pending when terminal
                _QUEUE_DEPTH.labels(status="RUNNING").dec()
                _QUEUE_DEPTH.labels(status="PENDING").dec()
                # Record duration
                with _job_start_lock:
                    start = _job_start.pop(entity_id, None)
                if start is not None:
                    _JOB_DURATION.observe(time.monotonic() - start)
            elif "RUNNING" in status_upper:
                _QUEUE_DEPTH.labels(status="PENDING").dec()
            return

        # ── Scenario created ──────────────────────────────────────────────────
        if "SCENARIO" in entity_type and "CREATION" in operation:
            _SCENARIOS_CREATED.inc()
            return

    except Exception:  # telemetry must never crash the app
        pass


def record_job_completion(job_id: str, stats: Optional[Dict[str, Any]]) -> None:
    """
    Record data-plane metrics once a PII job completes.

    Called from ``tasks.py`` (or ``_bg_job_done`` in app.py) after the
    anonymization function finishes, passing the ``job_stats`` dict.

    Parameters
    ----------
    job_id : str
        The application-level job identifier.
    stats  : dict or None
        The ``job_stats`` dict produced by ``run_pii_anonymization``.
        Expected keys: ``total_entities`` (int), ``processed_rows`` (int).
    """
    if not _PROM_AVAILABLE or not stats:
        return
    try:
        entities = int(stats.get("total_entities", 0) or 0)
        rows     = int(stats.get("processed_rows",  0) or 0)
        if entities > 0:
            _ENTITIES_DETECTED.inc(entities)
        if rows > 0:
            _ROWS_PROCESSED.inc(rows)
    except Exception:
        pass


def register_telemetry(event_processor: Any) -> None:
    """
    Subscribe the telemetry callback to the Taipy EventProcessor.

    Safe to call multiple times; only the first call registers.

    Parameters
    ----------
    event_processor : taipy.event.EventProcessor
        The running EventProcessor instance from app.py.
    """
    global _registered
    if _registered:
        return
    if not _PROM_AVAILABLE:
        _log.warning("[Telemetry] Skipping registration — prometheus_client not installed.")
        return
    try:
        event_processor.on_event(callback=_on_telemetry_event)
        _registered = True
        _log.info("[Telemetry] Registered Taipy event hook for Prometheus metrics.")
    except Exception as exc:
        _log.warning("[Telemetry] Failed to register event hook: %s", exc)


def start_metrics_server(port: int) -> None:
    """
    Start the Prometheus HTTP metrics server on *port*.

    Idempotent — subsequent calls with the same port are no-ops.

    Parameters
    ----------
    port : int
        TCP port to bind.  Grafana/Prometheus will scrape
        ``http://<host>:<port>/metrics``.
    """
    if not _PROM_AVAILABLE:
        _log.warning("[Telemetry] Cannot start metrics server — prometheus_client not installed.")
        return
    if port <= 0:
        return
    try:
        _prom_start_http_server(port)
        _log.info("[Telemetry] Prometheus metrics server listening on :%d/metrics", port)
    except OSError as exc:
        _log.warning("[Telemetry] Could not start metrics server on port %d: %s", port, exc)
