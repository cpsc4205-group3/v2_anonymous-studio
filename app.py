"""
Anonymous Studio — Main Application
CPSC 4205 | Group 3 | Spring 2026

Pages
  /dashboard  — live stats, pipeline overview, upcoming reviews
  /jobs       — submit datasets, monitor background jobs, download results
  /pipeline   — Kanban board linked to taipy.core scenario status
  /schedule   — appointment / review scheduling
  /audit      — immutable compliance audit log
"""
from __future__ import annotations
import os, io, time, uuid, warnings, tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore")

import pandas as pd
from taipy.gui import Gui, notify, invoke_long_callback
import taipy.core as tc
from taipy.core import Status

# ── Project modules ───────────────────────────────────────────────────────────
import core_config as cc          # boots Config + Orchestrator on import
from store import get_store, PipelineCard, Appointment, _now, _uid
from pii_engine import get_engine, ALL_ENTITIES, OPERATORS, OPERATOR_LABELS, SPACY_MODEL_STATUS, highlight_md
from tasks import PROGRESS_REGISTRY

store  = get_store()
engine = get_engine()

# ── Start the Orchestrator once ───────────────────────────────────────────────
cc.start_orchestrator()

# ═══════════════════════════════════════════════════════════════════════════════
#  STATE  (every variable below is reactive Taipy GUI state)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Navigation ────────────────────────────────────────────────────────────────
active_page = "dashboard"

# ── Quick-text PII (inline demo, no file upload needed) ──────────────────────
spacy_status = SPACY_MODEL_STATUS
qt_input  = (
    "Patient: Jane Doe, DOB: 03/15/1982\n"
    "SSN: 987-65-4321 | Email: jane.doe@hospital.org\n"
    "Phone: +1-800-555-0199 | Card: 4111-1111-1111-1111\n"
    "Physician: Dr. Robert Kim | IP: 192.168.1.101"
)
qt_operator        = "replace"
qt_operator_list   = OPERATORS
qt_threshold       = 0.35
qt_entities        = ALL_ENTITIES.copy()
qt_all_entities    = ALL_ENTITIES.copy()
qt_highlight_md    = ""
qt_anonymized      = ""
qt_entity_rows     = pd.DataFrame(columns=["Entity Type", "Text", "Confidence", "Span"])
qt_summary         = ""

# ── Job submission (large file) ───────────────────────────────────────────────
job_file_content   = None          # raw bytes of uploaded CSV / Excel
job_file_name      = ""
job_operator       = "replace"
job_operator_list  = OPERATORS
job_threshold      = 0.35
job_entities       = ALL_ENTITIES.copy()
job_all_entities   = ALL_ENTITIES.copy()
job_chunk_size     = 500
job_card_id        = ""            # link to a Kanban card
job_title          = "New Job"

# Job tracking table
job_table_data = pd.DataFrame(columns=["job_id", "Job ID", "Title", "Progress", "Status", "Entities", "Duration", "Message"])    # shown in Jobs page

# Per-job progress (polled every second while a job is running)
active_job_id        = ""          # job_config["job_id"] of the running job
active_scenario_id   = ""          # tc.Scenario.id
job_progress_pct     = 0
job_progress_msg     = "No job running."
job_progress_status  = ""          # running | done | error
job_is_running       = False

# Download
download_ready       = False
download_scenario_id = ""
download_rows        = 0
download_cols        = 0

# Preview table (first 50 rows of result)
preview_data       = pd.DataFrame()
preview_cols: List[str]  = []
stats_entity_rows  = pd.DataFrame(columns=["Entity Type", "Count"])

# ── Internal registry: job_id → scenario ─────────────────────────────────────
_SCENARIOS: Dict[str, Any] = {}    # job_id → tc.Scenario

# ── File upload cache (bytes must live outside Taipy state — state is JSON) ───
_FILE_CACHE: Dict[str, Any] = {"bytes": None, "name": ""}

# ── Pipeline (Kanban) ─────────────────────────────────────────────────────────
_CARD_COLS = ["id", "Title", "Priority", "Assignee", "Labels", "Job", "Attested", "Updated"]
kanban_backlog      = pd.DataFrame(columns=_CARD_COLS)
kanban_in_progress  = pd.DataFrame(columns=_CARD_COLS)
kanban_review       = pd.DataFrame(columns=_CARD_COLS)
kanban_done         = pd.DataFrame(columns=_CARD_COLS)
pipeline_all        = pd.DataFrame(columns=_CARD_COLS)
kanban_backlog_len     = 0
kanban_in_progress_len = 0
kanban_review_len      = 0
kanban_done_len        = 0

sel_card_id    = ""
card_form_open = False
card_id_edit   = ""
card_title_f   = ""
card_desc_f    = ""
card_status_f  = "backlog"
card_assign_f  = ""
card_priority_f = "medium"
card_labels_f  = ""
card_attest_f  = ""
card_status_opts   = ["backlog", "in_progress", "review", "done"]
card_priority_opts = ["low", "medium", "high", "critical"]

attest_open   = False
attest_cid    = ""
attest_note   = ""
attest_by     = ""

# ── Schedule ──────────────────────────────────────────────────────────────────
appt_table     = pd.DataFrame(columns=["id", "Title", "Date / Time", "Duration", "Attendees", "Linked Card", "Status"])
upcoming_table = pd.DataFrame(columns=["Title", "Date", "Time"])
appt_form_open = False
appt_id_edit   = ""
appt_title_f   = ""
appt_desc_f    = ""
appt_date_f    = ""
appt_time_f    = "10:00"
appt_dur_f     = 30
appt_att_f     = ""
appt_card_f    = ""
appt_status_f  = "scheduled"
appt_status_opts = ["scheduled", "completed", "cancelled"]
sel_appt_id    = ""

# ── Audit ─────────────────────────────────────────────────────────────────────
audit_table = pd.DataFrame(columns=["Time", "Actor", "Action", "Resource", "Details", "Severity"])
audit_search  = ""
audit_sev     = "all"
audit_sev_opts = ["all", "info", "warning", "critical"]

# ── Dashboard ─────────────────────────────────────────────────────────────────
dash_jobs_total     = 0
dash_jobs_running   = 0
dash_jobs_done      = 0
dash_jobs_failed    = 0
dash_cards_total    = 0
dash_cards_attested = 0
dash_upcoming_md    = ""
dash_recent_audit = pd.DataFrame(columns=["Time", "Action", "Details"])

# ═══════════════════════════════════════════════════════════════════════════════
#  REFRESH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _refresh_pipeline(state):
    by_s = store.cards_by_status()
    state.kanban_backlog     = _card_rows(by_s["backlog"])
    state.kanban_in_progress = _card_rows(by_s["in_progress"])
    state.kanban_review      = _card_rows(by_s["review"])
    state.kanban_done        = _card_rows(by_s["done"])
    state.pipeline_all       = _card_rows(store.list_cards())
    state.kanban_backlog_len     = len(by_s["backlog"])
    state.kanban_in_progress_len = len(by_s["in_progress"])
    state.kanban_review_len      = len(by_s["review"])
    state.kanban_done_len        = len(by_s["done"])


def _card_rows(cards):
    pmap = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    rows = []
    for c in cards:
        # sync job status from taipy.core if linked
        job_status = _resolve_job_status(getattr(c, 'scenario_id', None))
        rows.append({
            "id":        c.id,
            "Title":     c.title,
            "Priority":  f"{pmap.get(c.priority,'⚪')} {c.priority.title()}",
            "Assignee":  c.assignee or "—",
            "Labels":    ", ".join(c.labels) if c.labels else "—",
            "Job":       job_status,
            "Attested":  "✅" if c.attested else "⏳",
            "Updated":   c.updated_at[:10],
        })
    return pd.DataFrame(rows, columns=_CARD_COLS)


def _resolve_job_status(scenario_id: Optional[str]) -> str:
    """Map a taipy.core Scenario → human job status string."""
    if not scenario_id:
        return "—"
    try:
        sc = tc.get(scenario_id)
        jobs = [j for j in tc.get_jobs()
                if any(str(p.id) == scenario_id
                       for p in tc.get_parents(j).get("scenarios", []))]
        if not jobs:
            return "submitted"
        j = jobs[-1]
        m = {
            Status.COMPLETED: "✅ done",
            Status.RUNNING:   "🔄 running",
            Status.PENDING:   "⏳ pending",
            Status.FAILED:    "❌ failed",
            Status.CANCELED:  "🚫 cancelled",
        }
        return m.get(j.status, j.status.name.lower())
    except Exception:
        return "unknown"


def _refresh_appts(state):
    rows = []
    for a in store.list_appointments():
        smap = {"scheduled": "🗓️", "completed": "✅", "cancelled": "❌"}
        linked = ""
        if a.pipeline_card_id:
            c = store.get_card(a.pipeline_card_id)
            if c:
                linked = c.title
        rows.append({
            "id":          a.id,
            "Title":       a.title,
            "Date / Time": (a.scheduled_for.replace("T", " ")[:16]
                            if a.scheduled_for else "—"),
            "Duration":    f"{a.duration_mins} min",
            "Attendees":   ", ".join(a.attendees) if a.attendees else "—",
            "Linked Card": linked or "—",
            "Status":      f"{smap.get(a.status,'❓')} {a.status.title()}",
        })
    state.appt_table = pd.DataFrame(
        rows, columns=["id", "Title", "Date / Time", "Duration", "Attendees", "Linked Card", "Status"]
    )
    upcoming_rows = [
        {"Title": a.title,
         "Date":  a.scheduled_for[:10],
         "Time":  a.scheduled_for[11:16] if len(a.scheduled_for) > 10 else ""}
        for a in store.upcoming_appointments(6)
    ]
    state.upcoming_table = pd.DataFrame(upcoming_rows, columns=["Title", "Date", "Time"])


def _refresh_audit(state):
    sev  = state.audit_sev
    srch = (state.audit_search or "").lower()
    rows = []
    for e in store.list_audit():
        if sev != "all" and e.severity != sev:
            continue
        if srch and srch not in e.action.lower() and srch not in e.details.lower():
            continue
        smap = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        rows.append({
            "Time":     e.timestamp[11:19],
            "Actor":    e.actor,
            "Action":   e.action,
            "Resource": f"{e.resource_type}/{e.resource_id}",
            "Details":  e.details[:80],
            "Severity": f"{smap.get(e.severity,'ℹ️')} {e.severity}",
        })
    state.audit_table = pd.DataFrame(rows, columns=["Time", "Actor", "Action", "Resource", "Details", "Severity"])


def _refresh_job_table(state):
    rows = []
    for jid, sc in _SCENARIOS.items():
        prog = PROGRESS_REGISTRY.get(jid, {})
        pct  = prog.get("pct", 0)
        msg  = prog.get("message", "")
        sts  = prog.get("status", "running")
        stats_data = None
        try:
            stats_data = sc.job_stats.read()
        except Exception:
            pass
        entities = stats_data.get("total_entities", "—") if stats_data else "—"
        dur      = stats_data.get("duration_s", "—")     if stats_data else "—"
        rows.append({
            "job_id":     jid,
            "Job ID":     jid[:8],
            "Title":      stats_data.get("job_id", jid)[:24] if stats_data else jid[:24],
            "Progress":   f"{pct}%",
            "Status":     sts,
            "Entities":   entities,
            "Duration":   f"{dur}s" if dur != "—" else "—",
            "Message":    msg[:60],
        })
    state.job_table_data = pd.DataFrame(
        rows, columns=["job_id", "Job ID", "Title", "Progress", "Status", "Entities", "Duration", "Message"]
    )


def _refresh_dashboard(state):
    st = store.stats()
    state.dash_cards_total    = sum(st["pipeline_by_status"].values())
    state.dash_cards_attested = st["attested_cards"]
    all_jobs = tc.get_jobs()
    state.dash_jobs_total   = len(_SCENARIOS)
    state.dash_jobs_running = sum(1 for j in all_jobs if j.status == Status.RUNNING)
    state.dash_jobs_done    = sum(1 for j in all_jobs if j.status == Status.COMPLETED)
    state.dash_jobs_failed  = sum(1 for j in all_jobs if j.status == Status.FAILED)
    upcoming = store.upcoming_appointments(4)
    html = []
    for a in upcoming:
        dt = a.scheduled_for.replace("T", " ")[:16]
        html.append(f"**{a.title}**  \n{dt} · {a.duration_mins} min")
    if html:
        state.dash_upcoming_md = "  \n".join(html)
    else:
        state.dash_upcoming_md = "*No upcoming reviews scheduled.*"
    recent = [
        {"Time": e.timestamp[11:19], "Action": e.action, "Details": e.details[:55]}
        for e in store.list_audit(6)
    ]
    state.dash_recent_audit = pd.DataFrame(recent, columns=["Time", "Action", "Details"])


# ═══════════════════════════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

def on_init(state):
    _refresh_pipeline(state)
    _refresh_appts(state)
    _refresh_audit(state)
    _refresh_dashboard(state)
    _refresh_job_table(state)


# ── Navigation ────────────────────────────────────────────────────────────────
def go_dashboard(state, *_):
    state.active_page = "dashboard"
    _refresh_dashboard(state)

def go_qt(state, *_):
    state.active_page = "qt"

def go_jobs(state, *_):
    state.active_page = "jobs"
    _refresh_job_table(state)

def go_pipeline(state, *_):
    state.active_page = "pipeline"
    _refresh_pipeline(state)

def go_schedule(state, *_):
    state.active_page = "schedule"
    _refresh_appts(state)

def go_audit(state, *_):
    state.active_page = "audit"
    _refresh_audit(state)


# ── Quick-text PII ────────────────────────────────────────────────────────────
def on_qt_analyze(state):
    if not state.qt_input.strip():
        notify(state, "warning", "Enter some text first.")
        return
    ents = engine.analyze(state.qt_input, state.qt_entities, state.qt_threshold)
    state.qt_highlight_md = highlight_md(state.qt_input, ents)
    ent_rows0 = [
        {"Entity Type": e["entity_type"], "Text": e["text"],
         "Confidence": f"{e['score']:.0%}", "Span": f"{e['start']}–{e['end']}"}
        for e in ents
    ]
    state.qt_entity_rows = pd.DataFrame(ent_rows0, columns=["Entity Type", "Text", "Confidence", "Span"])
    state.qt_summary = (
        f"**{len(ents)}** PII entities found across "
        f"**{len(set(e['entity_type'] for e in ents))}** types."
        if ents else "✅ No PII detected."
    )
    if ents:
        notify(state, "warning", f"⚠️ {len(ents)} PII entities detected.")
    else:
        notify(state, "success", "✅ No PII detected.")


def on_qt_anonymize(state):
    if not state.qt_input.strip():
        notify(state, "warning", "Enter some text first.")
        return
    res = engine.anonymize(state.qt_input, state.qt_entities,
                           state.qt_operator, state.qt_threshold)
    state.qt_anonymized     = res.anonymized_text
    state.qt_highlight_md = highlight_md(state.qt_input, res.entities)
    ent_rows = [
        {"Entity Type": e["entity_type"], "Text": e["text"],
         "Confidence": f"{e['score']:.0%}",
         "Span": f"{e.get('start', '?')}–{e.get('end', '?')}"}
        for e in res.entities
    ]
    state.qt_entity_rows = pd.DataFrame(ent_rows, columns=["Entity Type", "Text", "Confidence", "Span"])
    state.qt_summary = f"**{res.total_found}** entities anonymized — {res.entity_summary}"
    store.log_user_action("user", "pii.anonymize.text", "session", _uid(),
              f"{res.total_found} entities via '{state.qt_operator}'")
    _refresh_audit(state)
    notify(state, "success", f"✅ {res.total_found} entities anonymized.")


def on_qt_load_sample(state):
    state.qt_input = (
        "Patient: Jane Doe, DOB: 03/15/1982\n"
        "SSN: 987-65-4321 | Email: jane.doe@hospital.org\n"
        "Phone: +1-800-555-0199 | Card: 4111-1111-1111-1111\n"
        "Physician: Dr. Robert Kim | IP: 192.168.1.101\n"
        "Passport: A12345678 | License: B2345678"
    )
    notify(state, "info", "Sample medical record loaded.")


def on_qt_clear(state):
    state.qt_input = ""
    state.qt_anonymized = ""
    state.qt_highlight_md = ""
    state.qt_entity_rows = pd.DataFrame(columns=["Entity Type", "Text", "Confidence", "Span"])
    state.qt_summary = ""


# ── File upload + background job submission ───────────────────────────────────
def on_file_upload(state, action, payload):
    """Called when user uploads a file — cache raw bytes outside Taipy state."""
    try:
        path = payload.get("path") or payload.get("file")
        if not path or not os.path.exists(path):
            return  # spurious / cancel callback — ignore silently
        with open(path, "rb") as f:
            raw = f.read()
        name = payload.get("name", os.path.basename(path))
        _FILE_CACHE["bytes"] = raw
        _FILE_CACHE["name"]  = name
        state.job_file_content = name   # non-None flag (str is JSON-safe)
        state.job_file_name = name
        notify(state, "success", f"📁 {name} ready.")
    except Exception as e:
        notify(state, "error", f"Upload error: {e}")


def _bg_submit_job(state_id, raw_df, config):
    """
    Runs in a background thread (via invoke_long_callback).
    Creates the Scenario, writes DataNodes, submits to Orchestrator.
    Returns (taipy_scenario_id, job_id) so _bg_job_done can update the card.
    """
    sc, sub = cc.submit_job(raw_df, config)
    _SCENARIOS[config["job_id"]] = sc
    return sc.id, config["job_id"]


def _bg_job_done(state, status, result):
    """Called by invoke_long_callback when the background thread finishes."""
    if result and isinstance(result, tuple) and len(result) == 2:
        taipy_sc_id, job_id = result
        for c in store.list_cards():
            if getattr(c, "job_id", None) == job_id:
                store.update_card(c.id, scenario_id=taipy_sc_id)
    _refresh_job_table(state)
    _refresh_dashboard(state)
    notify(state, "success", "✅ Job submitted to Orchestrator.")


def on_submit_job(state):
    """Validate inputs, parse the file, then fire invoke_long_callback."""
    # Resolve bytes from cache (preferred) or Taipy's bound variable (fallback)
    raw_bytes = _FILE_CACHE.get("bytes")
    if raw_bytes is None:
        fc = state.job_file_content
        if isinstance(fc, bytes):
            raw_bytes = fc
        elif isinstance(fc, str) and fc and os.path.exists(fc):
            with open(fc, "rb") as _f:
                raw_bytes = _f.read()
            _FILE_CACHE["bytes"] = raw_bytes
            _FILE_CACHE["name"]  = os.path.basename(fc)
    if not raw_bytes:
        notify(state, "warning", "Upload a CSV or Excel file first.")
        return

    # ── Parse file ────────────────────────────────────────────────────────────
    try:
        fname = (_FILE_CACHE.get("name") or state.job_file_name or "").lower()
        buf   = io.BytesIO(raw_bytes)
        if fname.endswith(".csv"):
            raw_df = pd.read_csv(buf)
        elif fname.endswith((".xlsx", ".xls")):
            raw_df = pd.read_excel(buf)
        else:
            notify(state, "error", "Unsupported file type. Use CSV or Excel.")
            return
    except Exception as e:
        notify(state, "error", f"Could not parse file: {e}")
        return

    if raw_df.empty:
        notify(state, "warning", "The uploaded file is empty.")
        return

    job_id = str(uuid.uuid4())[:12]
    config = {
        "job_id":      job_id,
        "operator":    state.job_operator,
        "entities":    state.job_entities,
        "threshold":   state.job_threshold,
        "text_columns": [],          # auto-detect
        "chunk_size":  state.job_chunk_size,
    }

    # Track progress state
    state.active_job_id       = job_id
    state.job_is_running      = True
    state.job_progress_pct    = 0
    state.job_progress_msg    = f"Queuing job for {len(raw_df):,} rows…"
    state.job_progress_status = "running"

    # Link to a Kanban card if selected
    if state.job_card_id:
        store.update_card(state.job_card_id,
                          status="in_progress",
                          job_id=job_id)
        store.log_user_action("user", "pipeline.link_job", "card", state.job_card_id,
                  f"Linked job {job_id}")

    store.log_user_action("user", "job.submit", "job", job_id,
              f"{len(raw_df):,} rows · {state.job_operator} · "
              f"{len(state.job_entities)} entity types")

    invoke_long_callback(
        state,
        user_function=_bg_submit_job,
        user_function_args=[None, raw_df, config],   # state_id filled by Taipy
        user_status_function=_bg_job_done,
    )

    _refresh_job_table(state)
    notify(state, "info", f"🚀 Job {job_id[:8]} submitted — "
           f"{len(raw_df):,} rows queued.")


def on_poll_progress(state):
    """Manual refresh — user clicks 'Refresh Progress' button."""
    jid = state.active_job_id
    if not jid:
        notify(state, "info", "No active job to poll.")
        return

    prog = PROGRESS_REGISTRY.get(jid, {})
    state.job_progress_pct    = prog.get("pct", 0)
    state.job_progress_msg    = prog.get("message", "Waiting…")
    state.job_progress_status = prog.get("status", "running")

    if prog.get("status") in ("done", "error"):
        state.job_is_running = False
        _load_job_results(state, jid)

    _refresh_job_table(state)
    _refresh_dashboard(state)


def _load_job_results(state, jid: str):
    sc = _SCENARIOS.get(jid)
    if not sc:
        return
    try:
        stats_data = sc.job_stats.read()
        anon_df    = sc.anon_output.read()
        if stats_data:
            ent_stat_rows = [
                {"Entity Type": k, "Count": v}
                for k, v in stats_data.get("entity_counts", {}).items()
            ]
            state.stats_entity_rows = pd.DataFrame(ent_stat_rows, columns=["Entity Type", "Count"])
        if anon_df is not None and not anon_df.empty:
            preview = anon_df.head(50)
            state.preview_data         = preview
            state.preview_cols         = list(preview.columns)
            state.download_ready       = True
            state.download_scenario_id = jid
            state.download_rows        = len(anon_df)
            state.download_cols        = len(anon_df.columns)
        # Move linked card to review
        for c in store.list_cards():
            if getattr(c, 'job_id', None) == jid and c.status == "in_progress":
                store.update_card(c.id, status="review")
                store.log_user_action("system", "pipeline.auto_move", "card", c.id,
                          f"Auto-moved to review after job {jid[:8]} completed")
        _refresh_pipeline(state)
        _refresh_audit(state)
    except Exception as e:
        notify(state, "error", f"Could not load results: {e}")


def on_select_job(state, var_name, value):
    if not value or not isinstance(value, list):
        return
    row = value[0] if isinstance(value[0], dict) else None
    if row:
        jid = row.get("job_id", "")
        state.active_job_id = jid
        prog = PROGRESS_REGISTRY.get(jid, {})
        state.job_progress_pct    = prog.get("pct", 0)
        state.job_progress_msg    = prog.get("message", "")
        state.job_progress_status = prog.get("status", "")
        _load_job_results(state, jid)


# ── Pipeline / Kanban ─────────────────────────────────────────────────────────
def on_card_new(state):
    state.card_id_edit = ""; state.card_title_f   = ""
    state.card_desc_f  = ""; state.card_status_f  = "backlog"
    state.card_assign_f = ""; state.card_priority_f = "medium"
    state.card_labels_f = ""; state.card_attest_f   = ""
    state.card_form_open = True


def on_card_save(state):
    if not state.card_title_f.strip():
        notify(state, "error", "Title is required."); return
    labels = [l.strip() for l in state.card_labels_f.split(",") if l.strip()]
    if state.card_id_edit:
        store.update_card(state.card_id_edit,
                          title=state.card_title_f, description=state.card_desc_f,
                          status=state.card_status_f, assignee=state.card_assign_f,
                          priority=state.card_priority_f, labels=labels,
                          attestation=state.card_attest_f)
        store.log_user_action("user", "pipeline.update", "card", state.card_id_edit,
                  f"Updated '{state.card_title_f}'")
        notify(state, "success", "Card updated.")
    else:
        c = PipelineCard(title=state.card_title_f, description=state.card_desc_f,
                         status=state.card_status_f, assignee=state.card_assign_f,
                         priority=state.card_priority_f, labels=labels,
                         attestation=state.card_attest_f)
        store.add_card(c)
        notify(state, "success", f"Card '{state.card_title_f}' created.")
    state.card_form_open = False
    _refresh_pipeline(state)
    _refresh_audit(state)


def on_card_cancel(state):
    state.card_form_open = False


def on_card_select(state, var_name, value):
    if value and isinstance(value, list) and isinstance(value[0], dict):
        state.sel_card_id = value[0].get("id", "")


def on_card_edit(state):
    cid = state.sel_card_id
    if not cid:
        notify(state, "warning", "Select a card first."); return
    c = store.get_card(cid)
    if not c:
        return
    state.card_id_edit   = c.id;    state.card_title_f    = c.title
    state.card_desc_f    = c.description
    state.card_status_f  = c.status; state.card_assign_f  = c.assignee
    state.card_priority_f = c.priority
    state.card_labels_f  = ", ".join(c.labels)
    state.card_attest_f  = c.attestation
    state.card_form_open = True


def on_card_forward(state):
    cid = state.sel_card_id
    if not cid:
        notify(state, "warning", "Select a card."); return
    c = store.get_card(cid)
    if not c:
        notify(state, "warning", "Card not found."); return
    order = ["backlog", "in_progress", "review", "done"]
    try:
        idx = order.index(c.status)
    except ValueError:
        idx = 0
    if idx < len(order) - 1:
        store.update_card(cid, status=order[idx + 1])
        notify(state, "success", f"→ {order[idx+1].replace('_',' ').title()}")
        _refresh_pipeline(state); _refresh_audit(state)
    else:
        notify(state, "info", "Already in Done.")


def on_card_back(state):
    cid = state.sel_card_id
    if not cid:
        notify(state, "warning", "Select a card."); return
    c = store.get_card(cid)
    if not c:
        notify(state, "warning", "Card not found."); return
    order = ["backlog", "in_progress", "review", "done"]
    try:
        idx = order.index(c.status)
    except ValueError:
        idx = len(order) - 1
    if idx > 0:
        store.update_card(cid, status=order[idx - 1])
        notify(state, "success", f"← {order[idx-1].replace('_',' ').title()}")
        _refresh_pipeline(state); _refresh_audit(state)
    else:
        notify(state, "info", "Already in Backlog.")


def on_card_delete(state):
    cid = state.sel_card_id
    if not cid:
        notify(state, "warning", "Select a card."); return
    store.delete_card(cid)
    state.sel_card_id = ""
    notify(state, "success", "Card deleted.")
    _refresh_pipeline(state); _refresh_audit(state)


def on_attest_open(state):
    if not state.sel_card_id:
        notify(state, "warning", "Select a card."); return
    state.attest_cid = state.sel_card_id
    state.attest_note = ""; state.attest_by = ""
    state.attest_open = True


def on_attest_confirm(state):
    if not state.attest_by.strip():
        notify(state, "error", "Name required."); return
    store.update_card(state.attest_cid, attested=True,
                      attested_by=state.attest_by, attested_at=_now(),
                      attestation=state.attest_note)
    state.attest_open = False
    notify(state, "success", "✅ Attestation recorded.")
    _refresh_pipeline(state); _refresh_audit(state)


def on_attest_cancel(state):
    state.attest_open = False


# ── Schedule ──────────────────────────────────────────────────────────────────
def on_appt_new(state):
    state.appt_id_edit = ""; state.appt_title_f = "PII Review"
    state.appt_desc_f  = ""; state.appt_date_f  = ""
    state.appt_time_f  = "10:00"; state.appt_dur_f = 30
    state.appt_att_f   = ""; state.appt_card_f   = ""
    state.appt_status_f = "scheduled"
    state.appt_form_open = True


def on_appt_save(state):
    if not state.appt_title_f.strip():
        notify(state, "error", "Title required."); return
    if not state.appt_date_f.strip():
        notify(state, "error", "Date required."); return
    sf   = f"{state.appt_date_f}T{state.appt_time_f}:00"
    atts = [a.strip() for a in state.appt_att_f.split(",") if a.strip()]
    if state.appt_id_edit:
        store.update_appointment(state.appt_id_edit,
                          title=state.appt_title_f, description=state.appt_desc_f,
                          scheduled_for=sf, duration_mins=state.appt_dur_f,
                          attendees=atts,
                          pipeline_card_id=state.appt_card_f or None,
                          status=state.appt_status_f)
        notify(state, "success", "Appointment updated.")
    else:
        a = Appointment(title=state.appt_title_f, description=state.appt_desc_f,
                        scheduled_for=sf, duration_mins=state.appt_dur_f,
                        attendees=atts,
                        pipeline_card_id=state.appt_card_f or None)
        store.add_appointment(a)
        notify(state, "success", f"'{a.title}' scheduled.")
    state.appt_form_open = False
    _refresh_appts(state); _refresh_audit(state)


def on_appt_cancel(state):
    state.appt_form_open = False


def on_appt_select(state, var_name, value):
    if value and isinstance(value, list) and isinstance(value[0], dict):
        state.sel_appt_id = value[0].get("id", "")


def on_appt_edit(state):
    aid = state.sel_appt_id
    if not aid:
        notify(state, "warning", "Select an appointment."); return
    a = store._appointments.get(aid)
    if not a:
        return
    parts = a.scheduled_for.split("T")
    state.appt_id_edit  = a.id; state.appt_title_f = a.title
    state.appt_desc_f   = a.description
    state.appt_date_f   = parts[0] if parts else ""
    state.appt_time_f   = parts[1][:5] if len(parts) > 1 else "10:00"
    state.appt_dur_f    = a.duration_mins
    state.appt_att_f    = ", ".join(a.attendees)
    state.appt_card_f   = a.pipeline_card_id or ""
    state.appt_status_f = a.status
    state.appt_form_open = True


def on_appt_delete(state):
    aid = state.sel_appt_id
    if not aid:
        notify(state, "warning", "Select an appointment."); return
    store.delete_appointment(aid)
    state.sel_appt_id = ""
    notify(state, "success", "Deleted.")
    _refresh_appts(state)


# ── Audit ─────────────────────────────────────────────────────────────────────
def on_audit_filter(state):
    _refresh_audit(state)

def on_audit_clear(state):
    state.audit_search = ""; state.audit_sev = "all"
    _refresh_audit(state)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap');
:root {
  /* GitHub Dark exact palette */
  --bg0:#0D1117;   /* canvas.default — page background */
  --bg1:#161B22;   /* canvas.subtle — nav, table headers */
  --bg2:#21262D;   /* canvas.inset — cards, inputs */
  --bdr:#30363D;   /* border.default */
  --bdr2:#21262D;  /* border.muted */

  /* GitHub semantic colors */
  --blu:#58A6FF;   /* accent.fg — links, primary actions */
  --blu-bg:#1F6FEB1A; /* accent.subtle bg */
  --grn:#3FB950;   /* success.fg */
  --grn-bg:#1A7F371A;
  --red:#F85149;   /* danger.fg */
  --red-bg:#DA36331A;
  --amb:#D29922;   /* attention.fg (warnings, in-progress) */
  --amb-bg:#9E6A031A;
  --pur:#BC8CFF;   /* done.fg */
  --pur-bg:#6E40C91A;

  /* Text */
  --txt:#E6EDF3;   /* fg.default */
  --txt2:#C9D1D9;  /* fg.muted — slightly dimmer body text */
  --mut:#8B949E;   /* fg.subtle — labels, hints */
  --mut2:#484F58;  /* fg.on-emphasis — very muted */
}

body,.taipy-container{
  background:var(--bg0)!important;
  color:var(--txt)!important;
  font-family:'Inter',system-ui,-apple-system,sans-serif!important;
  font-size:14px!important;
  line-height:1.5!important;
}

/* ── Nav ──────────────────────────────────────────────────────── */
.app-nav{
  display:flex;align-items:center;gap:4px;
  background:var(--bg1);
  border-bottom:1px solid var(--bdr);
  padding:8px 16px;
  position:sticky;top:0;z-index:200;
}
.app-logo{
  font-size:15px;font-weight:700;
  color:var(--txt);
  letter-spacing:-.3px;margin-right:16px;
  display:flex;align-items:center;gap:8px;
}
.app-logo-dot{
  width:10px;height:10px;border-radius:50%;
  background:var(--blu);display:inline-block;
}
.app-logo em{color:var(--mut);font-style:normal;font-weight:400;}

/* ── Layout ───────────────────────────────────────────── */
.MuiContainer-root{max-width:100%!important;padding-left:0!important;padding-right:0!important;}
.pg{padding:20px 24px;min-height:calc(100vh - 64px);}

/* ── Section headers ──────────────────────────────────────────── */
.sh{
  font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:.08em;
  color:var(--mut);
  border-bottom:1px solid var(--bdr);
  padding-bottom:8px;margin:24px 0 12px;
}

/* ── Metric cards ─────────────────────────────────────────────── */
.mc{
  background:var(--bg2);
  border:1px solid var(--bdr);
  border-radius:6px;
  padding:16px 20px;
  text-align:center;
  transition:border-color .15s;
}
.mc:hover{border-color:var(--blu);}
.mv{
  font-size:28px;font-weight:700;
  color:var(--txt);line-height:1.2;
  font-family:'IBM Plex Mono',monospace;
}
.mv-blue  {color:#58A6FF!important;}
.mv-purple{color:#BC8CFF!important;}
.mv-green {color:#3FB950!important;}
.mv-red   {color:#F85149!important;}
.mv-yellow{color:#D29922!important;}
.ml{
  font-size:11px;color:var(--mut);
  margin-top:4px;
}

/* ── Kanban columns ───────────────────────────────────────────── */
.nlp-banner{
  background:#161B22;
  border:1px solid #30363D;
  border-radius:6px;
  padding:8px 14px;
  margin-bottom:16px;
  font-size:12px;
  color:#8B949E;
}
.kh-gray  {color:#8B949E!important;}
.kh-purple{color:#BC8CFF!important;}
.kh-yellow{color:#D29922!important;}
.kh-green {color:#3FB950!important;}
.kc{
  background:var(--bg1);
  border:1px solid var(--bdr);
  border-radius:6px;
  padding:12px;
  min-height:360px;
}
.kh-cnt{font-size:11px;color:var(--mut);margin-bottom:6px;display:block;}
.kh{
  font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:.08em;
  padding-bottom:10px;
  border-bottom:1px solid var(--bdr);
  margin-bottom:10px;
  display:flex;align-items:center;gap:6px;
}
.kh-count{
  background:var(--bg2);
  border:1px solid var(--bdr);
  border-radius:10px;
  font-size:10px;padding:1px 7px;
  color:var(--mut);font-weight:500;
}

/* ── PII highlight box ────────────────────────────────────────── */
.hi-box{
  background:var(--bg1);
  border:1px solid var(--bdr);
  border-radius:6px;
  padding:12px 14px;
  font-family:'IBM Plex Mono',monospace;
  font-size:13px;line-height:1.8;min-height:100px;
  color:var(--txt2);
}

/* ── Anonymized output box ────────────────────────────────────── */
.anon-box{
  background:#0D1B12;
  border:1px solid #238636;
  border-radius:6px;
  padding:12px 14px;
  font-family:'IBM Plex Mono',monospace;
  font-size:13px;line-height:1.8;min-height:80px;
  color:#3FB950;
}

/* ── Progress box ─────────────────────────────────────────────── */
.prog-bar-wrap{
  background:var(--bg2);
  border:1px solid var(--bdr);
  border-radius:6px;
  padding:14px;margin:10px 0;
}

/* ── Status badges ────────────────────────────────────────────── */
.badge-blue{background:var(--blu-bg);color:var(--blu);
  border:1px solid var(--blu);border-radius:12px;padding:1px 8px;font-size:11px;}
.badge-green{background:var(--grn-bg);color:var(--grn);
  border:1px solid var(--grn);border-radius:12px;padding:1px 8px;font-size:11px;}
.badge-red{background:var(--red-bg);color:var(--red);
  border:1px solid var(--red);border-radius:12px;padding:1px 8px;font-size:11px;}
.badge-amber{background:var(--amb-bg);color:var(--amb);
  border:1px solid var(--amb);border-radius:12px;padding:1px 8px;font-size:11px;}

/* ── MUI overrides (Taipy uses Material UI internally) ─────────── */
.MuiTableCell-root{
  color:var(--txt2)!important;
  font-size:13px!important;
  font-family:'Inter',sans-serif!important;
  border-bottom:1px solid var(--bdr2)!important;
}
.MuiTableHead-root .MuiTableCell-root{
  color:var(--mut)!important;
  font-size:11px!important;
  font-weight:600!important;
  text-transform:uppercase;
  letter-spacing:.06em;
  background:var(--bg1)!important;
  border-bottom:1px solid var(--bdr)!important;
}
.MuiTableRow-root:hover{
  background:rgba(177,186,196,.06)!important;
}
.MuiTableRow-root:nth-of-type(odd){
  background:rgba(177,186,196,.02)!important;
}
.MuiInputBase-root,.MuiOutlinedInput-root{
  background:var(--bg2)!important;
  color:var(--txt)!important;
  border-radius:6px!important;
  font-family:'Inter',sans-serif!important;
  font-size:14px!important;
}
.MuiOutlinedInput-notchedOutline{
  border-color:var(--bdr)!important;
}
.Mui-focused .MuiOutlinedInput-notchedOutline{
  border-color:var(--blu)!important;
  box-shadow:0 0 0 3px #1F6FEB33!important;
}
label.MuiFormLabel-root{
  color:var(--mut)!important;
  font-family:'Inter',sans-serif!important;
  font-size:13px!important;
}
.MuiButton-containedPrimary{
  background:#1F6FEB!important;
  color:#fff!important;
  border-radius:6px!important;
  font-family:'Inter'!important;
  font-weight:600!important;
  font-size:13px!important;
  text-transform:none!important;
  box-shadow:none!important;
  border:1px solid #388BFD!important;
}
.MuiButton-containedPrimary:hover{
  background:#388BFD!important;
}
.MuiButton-outlinedPrimary{
  border-color:var(--bdr)!important;
  color:var(--txt2)!important;
  border-radius:6px!important;
  font-family:'Inter'!important;
  font-size:13px!important;
  text-transform:none!important;
  font-weight:500!important;
  background:var(--bg2)!important;
}
.MuiButton-outlinedPrimary:hover{
  background:rgba(177,186,196,.08)!important;
  border-color:var(--mut)!important;
}
.MuiDialog-paper{
  background:var(--bg2)!important;
  border:1px solid var(--bdr)!important;
  border-radius:8px!important;
  box-shadow:0 16px 32px rgba(1,4,9,.85)!important;
  color:var(--txt)!important;
}
.MuiSlider-root{color:var(--blu)!important;}
.MuiCheckbox-root,.MuiRadio-root{color:var(--mut)!important;}
.Mui-checked{color:var(--blu)!important;}
.MuiChip-root{
  background:var(--bg1)!important;
  border:1px solid var(--bdr)!important;
  color:var(--txt2)!important;
  font-size:12px!important;
}
.MuiLinearProgress-root{background:var(--bg2)!important;border-radius:3px!important;}
.MuiLinearProgress-bar{background:var(--blu)!important;}
.taipy-input .MuiFormControl-root,
.taipy-selector .MuiFormControl-root,
.taipy-number .MuiFormControl-root{margin-top:18px!important;}
.taipy-input.fullwidth .MuiFormControl-root{width:100%!important;}
</style>
"""

# ─── Dashboard ────────────────────────────────────────────────────────────────
DASH = """
<|part|class_name=pg|

<div class="sh">Overview</div>
<|layout|columns=1 1 1 1|gap=14px|
<|part|class_name=mc|
<|{dash_jobs_total}|text|class_name=mv mv-blue|>
<div class="ml">Jobs Submitted</div>
|>
<|part|class_name=mc|
<|{dash_jobs_running}|text|class_name=mv mv-purple|>
<div class="ml">Running Now</div>
|>
<|part|class_name=mc|
<|{dash_jobs_done}|text|class_name=mv mv-green|>
<div class="ml">Completed</div>
|>
<|part|class_name=mc|
<|{dash_jobs_failed}|text|class_name=mv mv-red|>
<div class="ml">Failed</div>
|>
|>

<|layout|columns=1 1|gap=14px|
<|part|class_name=mc|
<|{dash_cards_total}|text|class_name=mv mv-yellow|>
<div class="ml">Pipeline Cards</div>
|>
<|part|class_name=mc|
<|{dash_cards_attested}|text|class_name=mv mv-green|>
<div class="ml">Attested</div>
|>
|>

<|layout|columns=2 1|gap=24px|
<|part|
<div class="sh">Recent Audit Activity</div>
<|{dash_recent_audit}|table|columns=Time;Action;Details|page_size=6|show_all=False|>
|>
<|part|
<div class="sh">Upcoming Reviews</div>
<|{dash_upcoming_md}|text|mode=md|>
|>
|>

|>
"""

# ─── Jobs Page ────────────────────────────────────────────────────────────────
JOBS = """
<|part|class_name=pg|

<|part|class_name=nlp-banner|
🔬 NLP Engine: <|{spacy_status}|text|>
|>

<|layout|columns=3 2|gap=28px|

<|part|

<div class="sh">Submit Dataset for Background Anonymization</div>

<|{job_title}|input|label=Job title|class_name=fullwidth|>

<|{job_file_content}|file_selector|label=Upload CSV or Excel file|on_action=on_file_upload|extensions=.csv,.xlsx,.xls|>

<|{job_file_name}|text|>

<|layout|columns=1 1|gap=12px|
<|{job_operator}|selector|lov={job_operator_list}|dropdown=True|label=Operator|>
<|{job_threshold}|slider|min=0.1|max=1.0|step=0.05|label=Confidence threshold|>
|>
<|{job_threshold}|text|format=Threshold: %.2f|>

<|{job_chunk_size}|slider|min=100|max=5000|step=100|label=Chunk size (rows)|>
<|{job_chunk_size}|text|format=Chunk size: %d rows|>

<|{job_entities}|selector|lov={job_all_entities}|multiple=True|label=Entity types to detect|>

<|{job_card_id}|input|label=Link to Pipeline Card ID (optional)|class_name=fullwidth|>

<|🚀 Submit Background Job|button|on_action=on_submit_job|>

|>

<|part|

<div class="sh">Active Job Progress</div>

<|part|class_name=prog-bar-wrap|
Job: <|{active_job_id}|text|>
<|{job_progress_pct}|progress|>
<|{job_progress_msg}|text|>
<|{job_progress_status}|text|>
|>

<|🔄 Refresh Progress|button|on_action=on_poll_progress|>

<div class="sh" style="margin-top:16px">Results Preview</div>
<|{download_rows}|> rows · <|{download_cols}|> cols

<|{stats_entity_rows}|table|columns=Entity Type;Count|page_size=6|show_all=False|>

<|{preview_data}|table|page_size=8|show_all=False|>

|>

|>

<div class="sh">All Jobs</div>
<|{job_table_data}|table|columns=Job ID;Title;Progress;Status;Entities;Duration;Message|page_size=10|show_all=False|on_action=on_select_job|>

|>
"""

# ─── Pipeline ─────────────────────────────────────────────────────────────────
PIPELINE = """
<|part|class_name=pg|

<div class="sh">Pipeline Actions</div>

<|layout|columns=1 1 1 1 1 1|gap=8px|
<|＋ New Card|button|on_action=on_card_new|>
<|✏️ Edit|button|on_action=on_card_edit|class_name=secondary|>
<|◀ Back|button|on_action=on_card_back|class_name=secondary|>
<|Forward ▶|button|on_action=on_card_forward|class_name=secondary|>
<|🗑 Delete|button|on_action=on_card_delete|class_name=secondary|>
<|✅ Attest|button|on_action=on_attest_open|class_name=secondary|>
|>

Selected card: **<|{sel_card_id}|>**

<div class="sh">Board</div>

<|layout|columns=1 1 1 1|gap=14px|
<|part|class_name=kc|
<div class="kh kh-gray">📋 Backlog</div>
<|{kanban_backlog_len}|text|class_name=kh-cnt|>
<|{kanban_backlog}|table|columns=Title;Priority;Assignee;Job;Attested|show_all=False|page_size=10|on_action=on_card_select|>
|>
<|part|class_name=kc|
<div class="kh kh-purple">🔄 In Progress</div>
<|{kanban_in_progress_len}|text|class_name=kh-cnt|>
<|{kanban_in_progress}|table|columns=Title;Priority;Assignee;Job;Attested|show_all=False|page_size=10|on_action=on_card_select|>
|>
<|part|class_name=kc|
<div class="kh kh-yellow">👀 Review</div>
<|{kanban_review_len}|text|class_name=kh-cnt|>
<|{kanban_review}|table|columns=Title;Priority;Assignee;Job;Attested|show_all=False|page_size=10|on_action=on_card_select|>
|>
<|part|class_name=kc|
<div class="kh kh-green">✅ Done</div>
<|{kanban_done_len}|text|class_name=kh-cnt|>
<|{kanban_done}|table|columns=Title;Priority;Assignee;Job;Attested|show_all=False|page_size=10|on_action=on_card_select|>
|>
|>

<|{card_form_open}|dialog|title=Pipeline Card|on_action=on_card_cancel|width=600px|
<|{card_title_f}|input|label=Title *|class_name=fullwidth|>
<|{card_desc_f}|input|multiline=True|lines_shown=3|label=Description|class_name=fullwidth|>
<|layout|columns=1 1|gap=12px|
<|{card_status_f}|selector|lov={card_status_opts}|dropdown=True|label=Status|>
<|{card_priority_f}|selector|lov={card_priority_opts}|dropdown=True|label=Priority|>
|>
<|{card_assign_f}|input|label=Assignee|class_name=fullwidth|>
<|{card_labels_f}|input|label=Labels (comma-separated)|class_name=fullwidth|>
<|{card_attest_f}|input|multiline=True|lines_shown=2|label=Attestation Notes|class_name=fullwidth|>
<|layout|columns=1 1|gap=8px|
<|Save|button|on_action=on_card_save|>
<|Cancel|button|on_action=on_card_cancel|class_name=secondary|>
|>
|>

<|{attest_open}|dialog|title=Compliance Attestation|on_action=on_attest_cancel|width=480px|
<div style="color:#8B949E;margin-bottom:12px">This attestation is logged to the immutable audit trail.</div>
<|{attest_by}|input|label=Attested By *|class_name=fullwidth|>
<|{attest_note}|input|multiline=True|lines_shown=3|label=Statement|class_name=fullwidth|>
<|layout|columns=1 1|gap=8px|
<|Confirm|button|on_action=on_attest_confirm|>
<|Cancel|button|on_action=on_attest_cancel|class_name=secondary|>
|>
|>

<div class="sh">All Cards</div>
<|{pipeline_all}|table|columns=Title;Priority;Assignee;Job;Labels;Attested;Updated|show_all=False|page_size=10|>

|>
"""

# ─── Schedule ─────────────────────────────────────────────────────────────────
SCHEDULE = """
<|part|class_name=pg|

<|layout|columns=1 1 1|gap=8px|
<|＋ Schedule Review|button|on_action=on_appt_new|>
<|✏️ Edit|button|on_action=on_appt_edit|class_name=secondary|>
<|🗑 Delete|button|on_action=on_appt_delete|class_name=secondary|>
|>

<|layout|columns=2 1|gap=24px|
<|part|
<div class="sh">All Appointments</div>
<|{appt_table}|table|columns=Title;Date / Time;Duration;Attendees;Linked Card;Status|show_all=False|page_size=10|on_action=on_appt_select|>
|>
<|part|
<div class="sh">Upcoming</div>
<|{upcoming_table}|table|columns=Title;Date;Time|show_all=False|page_size=6|>
|>
|>

<|{appt_form_open}|dialog|title=Schedule Appointment|on_action=on_appt_cancel|width=580px|
<|{appt_title_f}|input|label=Title *|class_name=fullwidth|>
<|{appt_desc_f}|input|multiline=True|lines_shown=2|label=Description|class_name=fullwidth|>
<|layout|columns=1 1|gap=12px|
<|{appt_date_f}|input|label=Date (YYYY-MM-DD)|>
<|{appt_time_f}|input|label=Time (HH:MM)|>
|>
<|layout|columns=1 1|gap=12px|
<|{appt_dur_f}|number|label=Duration (min)|>
<|{appt_status_f}|selector|lov={appt_status_opts}|dropdown=True|label=Status|>
|>
<|{appt_att_f}|input|label=Attendees (comma-separated)|class_name=fullwidth|>
<|{appt_card_f}|input|label=Pipeline Card ID (optional)|class_name=fullwidth|>
<|layout|columns=1 1|gap=8px|
<|Save|button|on_action=on_appt_save|>
<|Cancel|button|on_action=on_appt_cancel|class_name=secondary|>
|>
|>

|>
"""

# ─── Audit ────────────────────────────────────────────────────────────────────
AUDIT = """
<|part|class_name=pg|

<div class="sh">Filter</div>
<|layout|columns=3 1 1 1|gap=12px|
<|{audit_search}|input|label=Search action / details|class_name=fullwidth|>
<|{audit_sev}|selector|lov={audit_sev_opts}|dropdown=True|label=Severity|>
<|Apply|button|on_action=on_audit_filter|>
<|Clear|button|on_action=on_audit_clear|class_name=secondary|>
|>

<|{audit_table}|table|columns=Time;Actor;Action;Resource;Details;Severity|show_all=False|page_size=20|>

|>
"""

# ─── Quick-text PII (inline) ──────────────────────────────────────────────────
QT = """
<|part|class_name=pg|

<|part|class_name=nlp-banner|
🔬 NLP Engine: <|{spacy_status}|text|>
|>

<|layout|columns=2 1|gap=24px|
<|part|

<div class="sh">Input</div>
<|{qt_input}|input|multiline=True|lines_shown=7|label=Paste text to analyze|class_name=fullwidth|>
<|layout|columns=1 1 1 1|gap=8px|
<|Sample|button|on_action=on_qt_load_sample|class_name=secondary|>
<|Clear|button|on_action=on_qt_clear|class_name=secondary|>
<|Analyze|button|on_action=on_qt_analyze|>
<|Anonymize|button|on_action=on_qt_anonymize|>
|>

<div class="sh">PII Highlights</div>
<|{qt_highlight_md}|text|mode=md|class_name=hi-box|>
<|{qt_summary}|text|>

<div class="sh">Anonymized Output</div>
<|{qt_anonymized}|text|class_name=anon-box|>

|>
<|part|

<div class="sh">Settings</div>
Operator
<|{qt_operator}|selector|lov={qt_operator_list}|dropdown=True|>
Confidence threshold: <|{qt_threshold}|text|format=%.2f|>
<|{qt_threshold}|slider|min=0.1|max=1.0|step=0.05|>
<div class="sh">Entity Types</div>
<|{qt_entities}|selector|lov={qt_all_entities}|multiple=True|>
<div class="sh">Detected Entities</div>
<|{qt_entity_rows}|table|columns=Entity Type;Text;Confidence;Span|show_all=False|page_size=8|>

|>
|>

|>
"""

# ─── Root page (nav + conditional renders) ────────────────────────────────────
ROOT = CSS + """
<|part|class_name=app-nav|
<span class="app-logo"><span class="app-logo-dot"></span>Anonymous<em>Studio</em></span>
<|Dashboard|button|on_action=go_dashboard|class_name=secondary|>
<|PII Text|button|on_action=go_qt|class_name=secondary|>
<|Upload & Jobs|button|on_action=go_jobs|class_name=secondary|>
<|Pipeline|button|on_action=go_pipeline|class_name=secondary|>
<|Schedule|button|on_action=go_schedule|class_name=secondary|>
<|Audit Log|button|on_action=go_audit|class_name=secondary|>
|>

<|part|render={active_page=="dashboard"}|
""" + DASH + """
|>
<|part|render={active_page=="qt"}|
""" + QT + """
|>
<|part|render={active_page=="jobs"}|
""" + JOBS + """
|>
<|part|render={active_page=="pipeline"}|
""" + PIPELINE + """
|>
<|part|render={active_page=="schedule"}|
""" + SCHEDULE + """
|>
<|part|render={active_page=="audit"}|
""" + AUDIT + """
|>
"""

# ═══════════════════════════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    gui = Gui(page=ROOT)
    try:
        gui.run(
            title="Anonymous Studio",
            host="0.0.0.0",
            port=5000,
            dark_mode=True,
            use_reloader=False,
            debug=False,
        )
    finally:
        cc.stop_orchestrator()
