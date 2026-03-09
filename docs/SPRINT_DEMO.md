# Sprint 2 Demo — Anonymous Studio v2

**Date:** 2026-03-08  
**Project:** Anonymous Studio v2 (Taipy GUI + taipy.core rewrite)  
**Team:** CPSC 4205 — Group 3

---

## Executive Summary

Anonymous Studio v2 is a **production-ready PII detection and anonymization platform** built on Taipy GUI with background job execution, multi-backend persistence, and full compliance tooling.

**Sprint 2 delivery: 20 features implemented across 8 pages, 10,600+ lines of application code, 239 tests.**

---

## What's Done — Feature Inventory

### ✅ Core PII Detection (6 features)

| # | Feature | Evidence | Demo |
|---|---------|----------|------|
| 1 | **Text input + detect + anonymize** | `app.py` → `on_qt_analyze()`, `on_qt_anonymize()` | Analyze page: paste text, click Analyze |
| 2 | **17 entity types** including ORGANIZATION | `pii_engine.py:193-198` → `ALL_ENTITIES` | Analyze page: entity selector checkboxes |
| 3 | **Confidence threshold slider** | `app.py` → `qt_threshold = 0.35` | Analyze page: drag slider 0–1 |
| 4 | **5 anonymization operators** (replace, redact, mask, hash, synthesize) | `pii_engine.py:220` + `services/synthetic.py` | Analyze page: operator dropdown |
| 5 | **Highlighted PII output** | `app.py` → `highlight_md()` | Analyze page: color-coded entity spans |
| 6 | **Entity findings table** (7 columns) | Entity type, text, confidence, band, span, recognizer, rationale | Analyze page: results table below output |

### ✅ Advanced PII Features (4 features)

| # | Feature | Evidence | Demo |
|---|---------|----------|------|
| 7 | **Allowlist** — exclude known-safe terms | `pii_engine.py` → `allow_list=` param | Analyze page: enter "John,Smith" in allowlist field |
| 8 | **Denylist** — force-flag custom terms | `pii_engine.py` → `CUSTOM_DENYLIST` entity + regex cache | Analyze page: enter "Acme Corp" in denylist field |
| 9 | **Detection rationale** | `pii_engine.py` → `return_decision_process=True` | Analyze page: "Rationale" column in entity table |
| 10 | **Synthesize operator** (Faker + LLM) | `services/synthetic.py` → Faker default, OpenAI/Azure optional | Analyze page: select "synthesize" operator |

### ✅ Batch Processing (2 features)

| # | Feature | Evidence | Demo |
|---|---------|----------|------|
| 11 | **CSV/Excel batch upload** | `app.py` → `on_file_upload()`, `on_submit_job()` | Jobs page: upload CSV → submit → monitor |
| 12 | **Background job execution** | `invoke_long_callback()` + `PROGRESS_REGISTRY` | Jobs page: progress bar updates, UI stays responsive |

### ✅ Pipeline Management (3 features)

| # | Feature | Evidence | Demo |
|---|---------|----------|------|
| 13 | **Kanban pipeline** (backlog → in_progress → review → done) | `app.py` → `on_card_new/edit/delete/forward/back` | Pipeline page: card CRUD + status transitions |
| 14 | **Pipeline burndown chart** | `app.py` → `_refresh_pipeline_burndown()` | Pipeline page: Plotly burndown graph |
| 15 | **Export pipeline data** (CSV/JSON) | `app.py:5179-5215` → `on_pipeline_export_csv/json()` | Pipeline page: Export buttons |

### ✅ Compliance & Audit (4 features)

| # | Feature | Evidence | Demo |
|---|---------|----------|------|
| 16 | **Full audit log** | `store.log_user_action()` called throughout app | Audit page: timestamped action trail |
| 17 | **Export audit logs** (CSV/JSON) | `app.py:5140-5176` → `on_audit_export_csv/json()` | Audit page: Export CSV / Export JSON buttons |
| 18 | **Compliance attestation** (Ed25519 signatures) | `services/attestation_crypto.py` → sign + verify | Pipeline page: Attest button on done cards |
| 19 | **Appointment scheduler** | `scheduler.py` → daemon thread, auto card advancement | Schedule page: create/edit/delete review appointments |

### ✅ Infrastructure (4 features)

| # | Feature | Evidence | Demo |
|---|---------|----------|------|
| 20 | **Multi-backend store** (Memory / MongoDB / DuckDB) | `store/` package → `get_store()` factory | `ANON_STORE_BACKEND=mongo` switches to MongoDB |
| 21 | **REST API** with Auth0 JWT | `rest_main.py` + `services/auth0_rest.py` | `taipy run rest_main.py` → API endpoints |
| 22 | **Prometheus telemetry** + Grafana | `services/telemetry.py` → metrics exporter | `ANON_METRICS_PORT=9090` → `/metrics` endpoint |
| 23 | **Dashboard** (KPIs, charts, live updates) | `app.py` → `_refresh_dashboard()` | Dashboard page: stats, stage pie, entity bars |

---

## Pages Available for Demo

| Page | URL | What to Show |
|------|-----|--------------|
| **Dashboard** | `/dashboard` | KPI tiles, stage distribution pie, entity bar chart, performance panel |
| **Analyze Text** | `/analyze` | Type/paste PII text → detect → anonymize with operator choice |
| **Batch Jobs** | `/jobs` | Upload CSV/Excel → submit background job → monitor progress |
| **Pipeline** | `/pipeline` | Kanban board: create cards, move forward/back, attest, export |
| **Schedule** | `/schedule` | Create compliance review appointments, link to cards |
| **Audit Log** | `/audit` | View all actions, filter by severity, export CSV/JSON |
| **UI Demo** | `/ui_demo` | Plotly chart playground (12+ chart types, real store data) |

---

## Demo Data (Pre-loaded)

The app seeds **15 pipeline cards** and **3 appointments** on startup for immediate demo:

### Pipeline Cards

| Card | Title | Status | Priority |
|------|-------|--------|----------|
| card-001 | Q1 Customer Export Anonymization | review | high |
| card-002 | HR Records PII Scrub | in_progress | critical |
| card-003 | Research Dataset Anonymization | done ✅ (attested) | medium |
| card-004 | Patient Records HIPAA Compliance | backlog | high |
| card-005 | Vendor Contract Data Review | backlog | low |
| card-006 | Allowlist / Denylist Support | done ✅ | medium |
| card-007 | Encrypt Operator Key Management | in_progress | medium |
| card-008 | ORGANIZATION Entity Support | done ✅ | low |
| card-009 | REST API for PII Detection | done ✅ | high |
| card-010 | MongoDB Persistence Layer | done ✅ | critical |
| card-011 | Export Audit Logs as CSV/JSON | done ✅ | medium |
| card-012 | Image PII Detection via OCR | backlog | low |
| card-013 | Role-Based Authentication | backlog | high |
| card-014 | Compliance Review Notifications | backlog | medium |
| card-015 | File Attachments on Pipeline Cards | backlog | medium |

### Appointments

| Appointment | Title | Date | Status |
|-------------|-------|------|--------|
| appt-001 | Q1 Export Compliance Review | 2026-03-05 | scheduled |
| appt-002 | HR Anonymization Sign-off | 2026-03-10 | scheduled |
| appt-003 | Research IRB Attestation | 2026-02-20 | completed |

---

## Demo Script (Suggested Flow)

### 1. Dashboard Overview (2 min)
- Open `/dashboard` — show KPI tiles (total jobs, attested cards, upcoming reviews)
- Point out stage distribution pie chart and entity breakdown bar
- Mention live-update capability

### 2. PII Detection & Anonymization (5 min)
- Navigate to `/analyze`
- Paste sample text: `"Contact John Smith at john.smith@acme.com or 555-867-5309. SSN: 123-45-6789."`
- Click **Analyze** — show highlighted entities with color coding
- Show entity findings table (7 columns including rationale)
- Change operator to **redact** → re-anonymize → show redacted output
- Change operator to **synthesize** → show Faker-generated replacements
- Demo **allowlist**: add "John" → re-analyze → "John" no longer flagged
- Demo **denylist**: add "Acme" → re-analyze → "Acme" flagged as CUSTOM_DENYLIST
- Adjust **threshold** slider → show confidence filtering

### 3. Batch Processing (3 min)
- Navigate to `/jobs`
- Upload a sample CSV with PII columns
- Submit job → show background progress
- Show result: anonymized CSV ready for download

### 4. Pipeline Management (3 min)
- Navigate to `/pipeline`
- Show Kanban columns with pre-loaded cards
- Create a new card → move it forward through statuses
- Show burndown chart
- Click **Export All CSV** → download pipeline data

### 5. Compliance (3 min)
- Navigate to `/schedule` — show upcoming appointments
- Navigate to `/audit` — show full audit trail
- Filter by severity
- Click **Export CSV** → download audit log
- Navigate back to `/pipeline` — show attested card (card-003) with signature

### 6. Infrastructure Highlights (2 min)
- Mention MongoDB persistence (`ANON_STORE_BACKEND=mongo`)
- Mention REST API (`taipy run rest_main.py`)
- Mention Prometheus telemetry (`/metrics` endpoint)
- Mention Auth0 JWT for API security

---

## Technical Stats

| Metric | Value |
|--------|-------|
| **Application code** | 10,618 lines across 20 Python files |
| **Main app** (`app.py`) | 5,610 lines, 71 callbacks |
| **PII engine** (`pii_engine.py`) | 570 lines, 17 entities, 5 operators |
| **Page definitions** | 849 lines of Taipy Markdown DSL |
| **Store backends** | 3 (Memory, MongoDB, DuckDB) |
| **Services** | 10 modules (auth, attestation, telemetry, synthetic, geo, jobs, progress) |
| **Tests** | 239 tests across 14 test files |
| **Pages** | 8 (dashboard, analyze, jobs, pipeline, schedule, audit, ui_demo, nav) |
| **CSS** | 25.7 KB custom dark theme stylesheet |
| **Charts** | 15+ Plotly chart types |

---

## What's In Progress / Backlog

### ⚠️ In Progress
- **card-007: Encrypt Operator** — Presidio supports it; needs UI key field and `OperatorConfig("encrypt")` integration

### 📋 Backlog (Future Sprints)
- **card-004:** Patient Records HIPAA Compliance (high)
- **card-005:** Vendor Contract Data Review (low)
- **card-012:** Image PII Detection via OCR (low)
- **card-013:** Role-Based Authentication (high)
- **card-014:** Compliance Review Notifications (medium)
- **card-015:** File Attachments on Pipeline Cards (medium)

---

## How to Run for Demo

```bash
# Quick start
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # recommended for NER entities
taipy run main.py
# Open http://localhost:5000
```

### With MongoDB (persistent data)
```bash
export ANON_STORE_BACKEND=mongo
export ANON_MONGO_URI=mongodb://localhost:27017/anon_studio
taipy run main.py
```

### With Telemetry
```bash
export ANON_METRICS_PORT=9090
taipy run main.py
# Prometheus metrics at http://localhost:9090/metrics
```

---

## Sprint 2 Summary

| Category | Done | In Progress | Backlog |
|----------|------|-------------|---------|
| Core PII Detection | 6 | 0 | 0 |
| Advanced PII | 4 | 0 | 0 |
| Batch Processing | 2 | 0 | 0 |
| Pipeline Management | 3 | 0 | 0 |
| Compliance & Audit | 4 | 0 | 0 |
| Infrastructure | 4 | 0 | 0 |
| Security | 0 | 1 (encrypt) | 1 (RBAC) |
| Future Enhancements | 0 | 0 | 4 |
| **Total** | **23** | **1** | **5** |

**Sprint 2 completion: 23/24 planned features delivered (95.8%).**

---

*Document generated for Sprint 2 demo presentation.*
