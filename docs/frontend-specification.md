# Anonymous Studio — Front-End Specification

> **Purpose:** Everything a Taipy GUI developer needs to know to rebuild the front end from the ground up.
> This document covers pages, state variables, callbacks, data models, services, styling, and component inventory — no design rationale, just what must be built.

---

## Table of Contents

1. [App Shell & Navigation](#1-app-shell--navigation)
2. [Pages](#2-pages)
   - [Dashboard](#21-dashboard)
   - [Analyze Text](#22-analyze-text-quick-test)
   - [Batch Jobs](#23-batch-jobs)
   - [Pipeline (Kanban)](#24-pipeline-kanban)
   - [Schedule (Reviews)](#25-schedule-reviews)
   - [Audit Log](#26-audit-log)
   - [Plotly UI Demo](#27-plotly-ui-demo)
3. [Dialogs](#3-dialogs)
4. [State Variable Inventory](#4-state-variable-inventory)
5. [Callback Inventory](#5-callback-inventory)
6. [Data Models](#6-data-models)
7. [Store API (Data Layer)](#7-store-api-data-layer)
8. [PII Engine API](#8-pii-engine-api)
9. [Services](#9-services)
10. [Background Job Flow](#10-background-job-flow)
11. [Taipy Core DataNodes](#11-taipy-core-datanodes)
12. [CSS & Theming](#12-css--theming)
13. [Assets](#13-assets)
14. [Notification Patterns](#14-notification-patterns)
15. [File Upload / Download Flows](#15-file-upload--download-flows)
16. [Live Dashboard Refresh](#16-live-dashboard-refresh)
17. [Component Inventory Summary](#17-component-inventory-summary)

---

## 1. App Shell & Navigation

### Entry Point

- `main.py` → calls `app.run_app()` → boots `Gui(pages=PAGES)`.
- `PAGES` dict lives in `pages/definitions.py` and maps route strings to Markdown DSL page strings.

### Route Map

| Route | Page Variable | Label |
|-------|--------------|-------|
| `/` | `NAV` | Root (menu navbar only) |
| `dashboard` | `DASH` | Dashboard |
| `analyze` | `QT` | Analyze Text |
| `jobs` | `JOBS` | Batch Jobs |
| `pipeline` | `PIPELINE` | Pipeline |
| `schedule` | `SCHEDULE` | Reviews |
| `audit` | `AUDIT` | Audit Log |
| `ui_demo` | `UI_DEMO` | Plotly UI |

### Menu

`menu_lov` is a list of `(route_string, Icon("images/<name>.svg"))` tuples powering the navbar.  
Navigation callback: `on_menu_action(state, id, payload)` → calls `navigate(state, page)` then invokes the page-specific `_refresh_*()` function.

### Per-Page CSS Scoping

Each page root `<|part|>` carries `class_name="pg pg-<page>"`. The generic `.pg` class handles base layout; `.pg-<page>` handles page-specific overrides.

---

## 2. Pages

### 2.1 Dashboard

**Purpose:** Live pipeline status, recent activity, and upcoming compliance reviews.

#### Toolbar
| Element | Type | State Variable | Callback |
|---------|------|----------------|----------|
| Refresh | button | — | `on_refresh_dashboard` |
| Generate Demo Session | button | — | `on_dash_seed_demo` |
| Report Mode | selector | `dash_report_mode` → `dash_report_mode_lov` | `on_dash_filters_change` |
| Time Window | selector | `dash_time_window` → `dash_time_window_lov` | `on_dash_filters_change` |
| Store Settings | button | — | `on_store_settings_open` |

#### KPI Ticker (6 items, horizontal flex)
| Metric | State Variable | Color |
|--------|----------------|-------|
| Jobs | `dash_jobs_total` | blue |
| Running | `dash_jobs_running` | purple |
| Done | `dash_jobs_done` | green |
| Failed | `dash_jobs_failed` | red |
| Cards | `dash_cards_total` | yellow |
| Attested | `dash_cards_attested` | green |

#### Conditional Sections

- **Upcoming Reviews** — markdown block `dash_upcoming_md`, visible when `dash_has_reviews` is true.
- **Pipeline Health** — `dash_completion_pct` (progress bar), `dash_inflight_cards`, `dash_backlog_cards`.
- **PII Entity Mix** — Plotly chart `dash_entity_mix_figure`, `dash_entity_dominance_pct`, `dash_kpi_entities_total`.
- **Geo Signal Map** — Plotly Scattermap `dash_map_figure`, location mention summary.
- **Pipeline Stage Distribution** — Plotly chart `dash_stage_figure`.
- **Top PII Entity Types** — Plotly chart `dash_entity_chart_figure`.
- **Pipeline Burndown** — Plotly chart `pipeline_burndown_figure`.
- **Engine Performance** — `dash_perf_avg_ms` metric, `dash_perf_count`, Plotly bar `dash_perf_figure`.
- **Last Upload Fingerprint** — SHA-256 ASCII art `job_file_art` + hash display.

---

### 2.2 Analyze Text (Quick Test)

**Purpose:** Paste or type text to detect and redact PII interactively.

#### Input Section
| Element | Type | State Variable | Notes |
|---------|------|----------------|-------|
| Text area | input (10 lines) | `qt_input` | Multiline |
| Entity types | multi-select (filter, dropdown) | `qt_entities` → `qt_all_entities` | 17 entity types |
| Detect PII | button | — | `on_qt_analyze` |
| Anonymize | button | — | `on_qt_anonymize` |
| Settings | button | — | `on_qt_settings_open` |
| Load Sample | button | — | `on_qt_load_sample` |
| Save Session | button | — | `on_qt_save_session` |
| Clear | button | — | `on_qt_clear` |

#### NLP Engine Banner
- `spacy_status` — text display showing current model status.

#### KPI Ticker (4 items)
| Label | State Variable | Color |
|-------|----------------|-------|
| Entities Detected | `qt_kpi_total_entities_ticker` | gray |
| Dominant Band | `qt_kpi_dominant_band_ticker` | purple |
| Avg Confidence | `qt_kpi_avg_confidence_ticker` | yellow |
| Low Confidence | `qt_kpi_low_confidence_ticker` | green |

#### Result Strip
- Summary: `qt_summary`
- Confidence Profile: `qt_confidence_md`
- Entity Mix: `qt_entity_breakdown_md`
- Confidence Bands: `qt_conf_bands_md`

#### Output (2-column layout)
| Column | Content | State Variable |
|--------|---------|----------------|
| Left — Detected PII | Color-coded markdown | `qt_highlight_md` |
| Right — Anonymized Output | Monospace raw text | `qt_anonymized_raw` |

- Download buttons: `on_qt_download_anonymized` (.txt), `on_qt_download_entities` (.csv).

#### Entity Evidence Table
- `qt_entity_rows` — columns: Entity Type, Text, Confidence, Confidence Band, Span, Recognizer, Rationale.
- `qt_entity_figure` — Plotly chart.

#### Saved Sessions Table
- `qt_sessions_data` — columns: ID, Title, Operator, Entities, Created.
- Load Session button → `on_qt_load_session`.

---

### 2.3 Batch Jobs

**Purpose:** Upload CSV or Excel files for bulk PII anonymization in the background.

#### Toolbar
| Element | Callback |
|---------|----------|
| Run Job | `on_submit_job` |
| Refresh | `on_poll_progress` |

#### KPI Metrics (4 items)
| Label | State Variable | Type |
|-------|----------------|------|
| Total | `job_kpi_total` | metric |
| Running | `job_kpi_running` | metric |
| Success % | `job_kpi_success_pct` | indicator (0–100%) |
| Entities | `job_kpi_entities` | metric |

#### Status Banner (3 LED indicators)
| Signal | LED Variable | Label Variable |
|--------|-------------|----------------|
| NLP Engine | `spacy_ok` | `spacy_status_label` |
| Store | `store_ok` | `store_status_label` |
| Raw DataNode | `raw_input_ok` | `raw_input_status_label` |

#### Upload & Config Panel
| Element | Type | State Variable |
|---------|------|----------------|
| File selector | file_selector | `job_file_content` (accepts `.csv, .xlsx, .xls`, max 50 MB) |
| File ready indicator | text | `job_file_name`, `job_file_hash` (SHA-256) |
| Operator | selector | `job_operator` → `job_operator_list` |
| Confidence threshold | slider (0.1–1.0) | `job_threshold` |
| Run Job | button | `on_submit_job` |
| Advanced Options | button | `on_job_adv_open` |

#### Advanced Options Pane (side panel, toggled by `job_adv_open`)
| Element | Type | State Variable |
|---------|------|----------------|
| Chunk size | slider (100–5000) | `job_chunk_size` |
| Link to Pipeline Card | input | `job_card_id` |
| NLP model | selector | `job_spacy_model` → `job_spacy_model_lov` |
| Entity types | multi-select | `job_entities` |
| Compute backend | selector | `job_compute_backend` → `job_compute_backend_lov` |
| Dask min rows | number | `job_dask_min_rows` |
| MongoDB write batch | number | `job_mongo_write_batch` |
| Close | button | `on_job_adv_close` |

#### Active Run Monitor
| Element | State Variable |
|---------|----------------|
| Run Health | `job_run_health` (metric) |
| Active Job ID | `active_job_id` (metric) |
| Submission ID | `job_active_submission_id` (metric) |
| Submission Status | `job_submission_status` (metric) |
| Stage | `job_stage_text` |
| ETA | `job_eta_text` |
| Processed | `job_processed_text` |

#### Tabbed Operational Views (`job_view_tab` / `job_view_tab_lov`)
| Tab | Key Elements |
|-----|-------------|
| **Results** | `job_quality_md`, entity stats table/chart (`stats_entity_rows`, `stats_entity_chart_figure`), download button (`on_download`), preview table (`preview_data`, first 50 rows) |
| **Job History** | `job_table_data` table (Job ID, Title, Progress, Status, Entities, Duration, Message), Cancel (`on_job_cancel`) / Remove (`on_job_remove`) buttons |
| **Data Nodes** | `selected_data_node` selector + data node inspector |
| **Errors / Audit** | `job_errors_data` table |
| **Task Orchestration** | `orchestration_scenario` selector + scenario inspector, `orchestration_job` selector |
| **What-if Analysis** | `whatif_scenarios_sel` (multi-select), Compare button (`on_whatif_compare`), comparison table (`whatif_compare_data`) / chart (`whatif_compare_figure`) |
| **Submission Monitor** | `submission_table` (Submission, Entity, Status, Jobs, Created) |
| **Cycle Monitor** | `cycle_table` (Cycle, Frequency, Start, End, Scenarios) |

---

### 2.4 Pipeline (Kanban)

**Purpose:** Track de-identification tasks through the compliance workflow.

#### Board Actions Toolbar
| Button | Callback |
|--------|----------|
| New Card | `on_card_new` |
| Edit Card | `on_card_edit` |
| Delete | `on_card_delete` |
| ◀ Back | `on_card_back` |
| Forward ▶ | `on_card_forward` |
| Attest | `on_attest_open` |
| View History | `on_card_history` |

#### Card Info Display
- `pipeline_front_md` — markdown info about the board.
- `pipeline_selected_md` — details for the currently selected card.

#### Kanban Board (4-column table layout)

| Column | Color | Table Variable | Count Variable | Selection Variable |
|--------|-------|----------------|----------------|-------------------|
| Backlog | gray | `kanban_backlog` | `kanban_backlog_len` | `backlog_sel` |
| In Progress | purple | `kanban_in_progress` | `kanban_in_progress_len` | `in_progress_sel` |
| Review | yellow | `kanban_review` | `kanban_review_len` | `review_sel` |
| Done | green | `kanban_done` | `kanban_done_len` | `done_sel` |

Table columns per board: Select (checkbox), Title, Priority, Job.

#### Burndown Chart
- `pipeline_burndown_figure` — Plotly chart.
- `pipeline_burndown_md` — summary text.
- Visible when `pipeline_burndown_visible` is true.

#### All Cards Table
- `pipeline_all` — columns: Title, Priority, Assignee, Job, Labels, Attested, Updated.
- Cell colors based on Priority and Job status.

#### Export
- Export All CSV button → `on_pipeline_export_csv`.
- Export All JSON button → `on_pipeline_export_json`.

---

### 2.5 Schedule (Reviews)

**Purpose:** Schedule and track compliance review appointments linked to pipeline cards.

#### Actions
| Button | Callback |
|--------|----------|
| New Review | `on_appt_new` |
| Edit | `on_appt_edit` |
| Delete | `on_appt_delete` |

#### Status Legend (chips)
- Scheduled, Completed, Cancelled — styled with `.schedule-chip`, `.chip-scheduled`, `.chip-completed`, `.chip-cancelled`.

#### Two-Column Layout
| Column | Table Variable | Columns |
|--------|----------------|---------|
| All Appointments | `appt_table` | Title, Date/Time, Duration, Attendees, Linked Card, Status |
| Upcoming | `upcoming_table` | Title, Date, Time |

#### System Requirements Panel
- Dask status: `dask_status`.
- NLP Engine status: `spacy_status_label`.
- Store Backend status: `store_status_label`.

---

### 2.6 Audit Log

**Purpose:** Immutable record of every action taken in the system.

#### Filter Section
| Element | Type | State Variable | Callback |
|---------|------|----------------|----------|
| Search | text input | `audit_search` | — |
| Severity | selector | `audit_sev` → `audit_sev_opts` (all/info/warning/critical) | — |
| Apply | button | — | `on_audit_filter` |
| Clear | button | — | `on_audit_clear` |

#### Audit Table
- `audit_table` — columns: Time, Actor, Action, Resource, Details, Severity.
- Severity column colored via cell class names.

#### Export
- Export CSV button → `on_audit_export_csv`.
- Export JSON button → `on_audit_export_json`.

---

### 2.7 Plotly UI Demo

**Purpose:** Interactive showcase of Plotly + Taipy chart options.

#### Playground Controls
| Element | Type | State Variable |
|---------|------|----------------|
| Plot type | selector | `ui_plot_type` → `ui_plot_type_lov` |
| Orientation | selector (conditional) | `ui_plot_orientation` → `ui_plot_orientation_lov` |
| Bar mode | selector (conditional) | `ui_plot_barmode` → `ui_plot_barmode_lov` |
| Trace mode | selector (conditional) | `ui_plot_trace_mode` → `ui_plot_trace_mode_lov` |
| Palette | selector | `ui_plot_palette` → `ui_plot_palette_lov` |
| Theme | selector | `ui_plot_theme` → `ui_plot_theme_lov` |
| Legend | selector | `ui_plot_show_legend` → `ui_plot_show_legend_lov` |
| Catalog mode | selector | `ui_demo_mode` → `ui_demo_mode_lov` |
| Top N | number input | `ui_demo_top_n` |
| Refresh | button | `on_ui_demo_refresh` |
| Demo Session | button | `on_dash_seed_demo` |

#### Chart Playground
- `ui_plot_playground_figure` — Plotly chart.
- `ui_plot_option_rows` — table (Option, Value, Description).

#### Plotly Catalog (6 charts, conditionally rendered)
1. Pareto — `ui_demo_pareto_figure`
2. Treemap — `ui_demo_treemap_figure`
3. Box Plot — `ui_demo_conf_box_figure`
4. Heatmap — `ui_demo_heatmap_figure`
5. Timeline — `ui_demo_timeline_figure`
6. Pipeline Distribution — `ui_demo_pipeline_figure`

#### Geo Signal Map
- `ui_demo_map_figure` — Plotly Scattermap.
- `ui_demo_map_md` — summary markdown.

#### Underlying Data Tables
- Entity stats: `ui_demo_entity_table` (Entity Type, Count, Share %, Cumulative %).
- Evidence: `ui_demo_evidence_table` (Entity Type, Confidence, Recognizer, Text).
- Pipeline: `ui_demo_pipeline_table` (Stage, Count).

---

## 3. Dialogs

### 3.1 Store Settings Dialog
- Trigger: `on_store_settings_open` → `store_settings_open = True`.
- Fields:
  - Backend selector: `store_backend_sel` → `store_backend_lov`.
  - MongoDB URI input: `store_mongo_uri`.
  - DuckDB path input: `store_duckdb_path`.
  - Message area: `store_settings_msg`.
- Buttons: Apply (`on_store_apply`), Cancel (`on_store_settings_close`).

### 3.2 Card Form Dialog
- Trigger: `on_card_new` or `on_card_edit` → `card_form_open = True`.
- Fields:

| Field | State Variable | Type | Required |
|-------|----------------|------|----------|
| Title | `card_title_f` | input | ✱ |
| Description | `card_desc_f` | input | |
| Status | `card_status_f` → `card_status_opts` | selector | |
| Priority | `card_priority_f` → `card_priority_opts` | selector | |
| Type | `card_type_f` → `card_type_opts` | selector | |
| Data Source | `card_source_f` | input | |
| Assignee | `card_assign_f` | input | |
| Labels | `card_labels_f` | input | |
| Session link | `card_session_f` → `card_session_opts` | selector | |
| Attestation notes | `card_attest_f` | input | |

- Hidden state: `card_id_edit` (empty = new, non-empty = edit).
- Buttons: Save (`on_card_save`), Cancel (`on_card_cancel`).

### 3.3 Attestation Dialog
- Trigger: `on_attest_open` → `attest_open = True`.
- Fields:
  - Attested By: `attest_by` (required).
  - Statement: `attest_note` (multiline).
- Hidden state: `attest_cid` (card ID being attested).
- Buttons: Confirm (`on_attest_confirm`), Cancel (`on_attest_cancel`).

### 3.4 Card History Dialog
- Trigger: `on_card_history` → `card_audit_open = True`.
- Content:
  - Sessions table: `card_sessions_data` (ID, Title, Operator, Entities, Source, Created).
  - Audit trail table: `card_audit_data` (Time, Action, Actor, Details).
- Button: Close (`on_card_history_close`).

### 3.5 Appointment Form Dialog
- Trigger: `on_appt_new` or `on_appt_edit` → `appt_form_open = True`.
- Fields:

| Field | State Variable | Type | Required |
|-------|----------------|------|----------|
| Title | `appt_title_f` | input | ✱ |
| Description | `appt_desc_f` | input | |
| Date | `appt_date_f` | date picker | |
| Time | `appt_time_f` | input (HH:MM) | |
| Duration (min) | `appt_dur_f` | number | |
| Status | `appt_status_f` → `appt_status_opts` | selector | |
| Attendees | `appt_att_f` | input | |
| Pipeline Card ID | `appt_card_f` | input | |

- Hidden state: `appt_id_edit` (empty = new, non-empty = edit).
- Buttons: Save (`on_appt_save`), Cancel (`on_appt_cancel`).

### 3.6 Detection Settings Dialog (Analyze Text page)
- Trigger: `on_qt_settings_open` → `qt_settings_open = True`.
- Fields:

| Field | State Variable | Type |
|-------|----------------|------|
| NER model | `qt_ner_model_sel` → `qt_ner_model_lov` | selector |
| Other model | `qt_ner_other_model` | input (conditional) |
| Operator | `qt_operator` → `qt_operator_list` | selector |
| Confidence threshold | `qt_threshold` | slider |
| Entity types | `qt_entities` | multi-select |
| Allowlist | `qt_allowlist_text` | input (comma-separated) |
| Denylist | `qt_denylist_text` | input (comma-separated) |
| **Synthetic section** (conditional on `qt_operator == "synthesize"`) | | |
| Provider | `qt_synth_provider` → `qt_synth_provider_lov` | selector |
| Model name | `qt_synth_model` | input |
| Azure deployment | `qt_synth_deployment` | input |
| Azure endpoint | `qt_synth_api_base` | input |
| API version | `qt_synth_api_version` | input |
| OpenAI base URL | `qt_synth_api_base` | input |
| API key | `qt_synth_api_key` | password input |
| Temperature | `qt_synth_temperature` | slider (0–2) |
| Max tokens | `qt_synth_max_tokens` | slider (128–4000) |

- Buttons: Apply (`on_qt_settings_close`), Close (`on_qt_settings_close`).

---

## 4. State Variable Inventory

### Navigation
| Variable | Type | Default |
|----------|------|---------|
| `active_page` | `str` | `"dashboard"` |
| `menu_lov` | `List[Tuple[str, Icon]]` | 7 entries |

### System Status
| Variable | Type | Purpose |
|----------|------|---------|
| `spacy_status` | `str` | Full status string |
| `spacy_status_label` | `str` | Compact label |
| `spacy_ok` | `bool` | LED widget |
| `spacy_model_sel` | `str` | Current model choice |
| `spacy_model_lov` | `List[str]` | Available models |
| `store_status` | `str` | Store backend description |
| `store_status_label` | `str` | Compact label |
| `store_ok` | `bool` | LED widget |
| `raw_input_status_label` | `str` | Raw DataNode status |
| `raw_input_ok` | `bool` | LED widget |
| `dask_status` | `str` | Dask availability text |

### Store Settings
| Variable | Type |
|----------|------|
| `store_backend_sel` | `str` — `"memory"` / `"duckdb"` / `"mongo"` |
| `store_backend_lov` | `List[str]` |
| `store_mongo_uri` | `str` |
| `store_duckdb_path` | `str` |
| `store_settings_open` | `bool` |
| `store_settings_msg` | `str` |

### Quick Text Analysis (~40 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `qt_input` | `str` | Multiline user input |
| `qt_operator` | `str` | replace/redact/mask/hash/synthesize |
| `qt_operator_list` | `List[str]` | Available operators |
| `qt_threshold` | `float` | Confidence threshold (default 0.35) |
| `qt_entities` | `List[str]` | Selected entity types |
| `qt_all_entities` | `List[str]` | All 17 entity types |
| `qt_highlight_md` | `str` | Color-coded PII markdown |
| `qt_anonymized` | `str` | Markdown anonymized output |
| `qt_anonymized_raw` | `str` | Raw anonymized text |
| `qt_entity_rows` | `DataFrame` | Entity evidence table |
| `qt_entity_figure` | `Dict` | Plotly figure |
| `qt_summary` | `str` | Result summary markdown |
| `qt_confidence_md` | `str` | Confidence profile markdown |
| `qt_entity_breakdown_md` | `str` | Entity mix markdown |
| `qt_conf_bands_md` | `str` | Confidence bands markdown |
| `qt_kpi_total_entities` | `int` | Entity count |
| `qt_kpi_dominant_band` | `str` | Most common confidence band |
| `qt_kpi_avg_confidence` | `str/float` | Mean confidence |
| `qt_kpi_low_confidence` | `int` | Low-confidence count |
| `qt_kpi_*_ticker` | `str` | Display versions of KPIs |
| `qt_has_entities` | `bool` | Visibility flag |
| `qt_settings_open` | `bool` | Settings dialog |
| `qt_allowlist_text` | `str` | Comma-separated allowlist |
| `qt_denylist_text` | `str` | Comma-separated denylist |
| `qt_ner_model_sel` | `str` | NER model selection |
| `qt_ner_model_lov` | `List[str]` | Model options |
| `qt_ner_other_model` | `str` | Custom model name |
| `qt_synth_provider` | `str` | faker/openai/azure_openai |
| `qt_synth_model` | `str` | LLM model name |
| `qt_synth_api_key` | `str` | API key (password) |
| `qt_synth_api_base` | `str` | API base URL |
| `qt_synth_deployment` | `str` | Azure deployment name |
| `qt_synth_api_version` | `str` | API version |
| `qt_synth_temperature` | `float` | 0.2 default |
| `qt_synth_max_tokens` | `int` | 800 default |
| `qt_sessions_data` | `DataFrame` | Saved sessions table |
| `qt_selected_session` | `str` | Selected session ID |

### Job Submission (~35 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `job_file_content` | `str/None` | Filename string (flag for file readiness) |
| `job_file_name` | `str` | Uploaded file name |
| `job_file_hash` | `str` | SHA-256 hex |
| `job_file_art` | `str` | Drunken Bishop ASCII art fingerprint |
| `job_operator` | `str` | Selected operator |
| `job_operator_list` | `List[str]` | Operator options |
| `job_threshold` | `float` | Confidence threshold |
| `job_entities` | `List[str]` | Selected entity types |
| `job_chunk_size` | `int` | Chunk size (default 500) |
| `job_compute_backend` | `str` | auto/pandas/dask |
| `job_dask_min_rows` | `int` | Min rows for Dask (default 250000) |
| `job_mongo_write_batch` | `int` | MongoDB batch size (default 5000) |
| `job_card_id` | `str` | Optional pipeline card link |
| `job_table_data` | `DataFrame` | Job history table |
| `active_job_id` | `str` | Currently active job |
| `job_active_submission_id` | `str` | Taipy submission ID |
| `job_submission_status` | `str` | Submission status text |
| `job_progress_pct` | `int` | Progress percentage |
| `job_progress_msg` | `str` | Progress message |
| `job_progress_status` | `str` | running/done/error |
| `job_is_running` | `bool` | Running flag |
| `download_ready` | `bool` | Results available |
| `download_scenario_id` | `str` | Scenario to download from |
| `preview_data` | `DataFrame` | Preview (50 rows) |
| `stats_entity_rows` | `DataFrame` | Entity Type × Count |
| `stats_entity_chart_figure` | `Dict` | Plotly chart |
| `job_quality_md` | `str` | Result quality summary |
| `job_kpi_total/running/success_pct/entities` | various | KPI values |
| `job_run_health` | `str` | Idle/Running/Error |
| `job_stage_text` | `str` | Current stage text |
| `job_eta_text` | `str` | ETA text |
| `job_processed_text` | `str` | Processed count text |
| `job_adv_open` | `bool` | Advanced pane toggle |
| `job_view_tab` | `str` | Active tab |
| `job_view_tab_lov` | `List[str]` | Tab options |

### Orchestration & What-if
| Variable | Type |
|----------|------|
| `orchestration_scenario` | `Any` (Taipy Scenario) |
| `orchestration_job` | `Any` (Taipy Job) |
| `whatif_scenarios_lov` | `List[str]` |
| `whatif_scenarios_sel` | `List[str]` |
| `whatif_compare_data` | `DataFrame` |
| `whatif_compare_figure` | `Dict` |
| `whatif_compare_has_data` | `bool` |
| `submission_table` | `DataFrame` |
| `cycle_table` | `DataFrame` |

### Pipeline / Kanban (~30 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `kanban_backlog` | `DataFrame` | Backlog column table |
| `kanban_in_progress` | `DataFrame` | In Progress column table |
| `kanban_review` | `DataFrame` | Review column table |
| `kanban_done` | `DataFrame` | Done column table |
| `kanban_*_len` | `int` | Column item counts |
| `pipeline_all` | `DataFrame` | All cards flat table |
| `pipeline_burndown` | `DataFrame` | Burndown data |
| `pipeline_burndown_figure` | `Dict` | Plotly burndown chart |
| `pipeline_burndown_visible` | `bool` | Visibility |
| `pipeline_burndown_md` | `str` | Summary text |
| `pipeline_front_md` | `str` | Board info markdown |
| `pipeline_selected_md` | `str` | Selected card markdown |
| `sel_card_id` | `str` | Selected card ID |
| `sel_card_title` | `str` | Selected card title |
| `sel_card_short_id` | `str` | Truncated ID |
| `backlog_sel` / `in_progress_sel` / `review_sel` / `done_sel` | `List[str]` | Row selections |
| `card_form_open` | `bool` | Card form dialog toggle |
| `card_id_edit` | `str` | Editing card ID (empty = new) |
| `card_title_f` through `card_attest_f` | `str` | Form fields |
| `card_status_opts` / `card_priority_opts` / `card_type_opts` | `List[str]` | Dropdown options |
| `card_session_f` / `card_session_opts` | `str` / `List[str]` | Session link |
| `attest_open` | `bool` | Attestation dialog |
| `attest_cid` / `attest_note` / `attest_by` | `str` | Attestation fields |
| `card_audit_open` | `bool` | History dialog |
| `card_audit_data` | `DataFrame` | Audit trail for card |
| `card_sessions_data` | `DataFrame` | Sessions for card |

### Schedule / Appointments
| Variable | Type |
|----------|------|
| `appt_table` | `DataFrame` |
| `upcoming_table` | `DataFrame` |
| `appt_form_open` | `bool` |
| `appt_id_edit` | `str` |
| `appt_title_f` through `appt_card_f` | `str` / `date` / `int` |
| `appt_status_opts` | `List[str]` |
| `sel_appt_id` | `str` |

### Audit Log
| Variable | Type |
|----------|------|
| `audit_table` | `DataFrame` |
| `audit_search` | `str` |
| `audit_sev` | `str` |
| `audit_sev_opts` | `List[str]` |

### Dashboard (~50 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `dash_jobs_total/running/done/failed` | `int` | Job counts |
| `dash_cards_total/attested` | `int` | Card counts |
| `dash_upcoming_md` | `str` | Upcoming reviews markdown |
| `dash_stage_chart` / `dash_stage_figure` | `DataFrame` / `Dict` | Stage breakdown |
| `dash_entity_chart` / `dash_entity_mix_figure` / `dash_entity_chart_figure` | `DataFrame` / `Dict` | Entity charts |
| `dash_entity_dominance_pct` | `float` | Top entity share |
| `dash_completion_pct` | `float` | Pipeline completion (0–100) |
| `dash_inflight_cards` / `dash_backlog_cards` | `int` | Pipeline counts |
| `dash_report_mode` / `dash_time_window` | `str` | Filter selections |
| `dash_report_mode_lov` / `dash_time_window_lov` | `List[str]` | Filter options |
| `dash_map_chart` / `dash_map_figure` | `DataFrame` / `Dict` | Geo map data |
| `dash_perf_avg_ms` / `dash_perf_count` / `dash_perf_figure` | various | Engine performance |
| `dash_*_visible` | `bool` | Conditional rendering flags |
| `dash_has_reviews` / `dash_has_any_data` | `bool` | Visibility |

### UI Demo / Plotly Playground (~25 variables)
| Variable | Type |
|----------|------|
| `ui_demo_mode` / `ui_demo_mode_lov` | `str` / `List[str]` |
| `ui_demo_top_n` | `int` |
| `ui_demo_*_figure` (7 figures) | `Dict` |
| `ui_demo_entity_table` / `ui_demo_evidence_table` / `ui_demo_pipeline_table` | `DataFrame` |
| `ui_plot_type` / `ui_plot_*_lov` | `str` / `List[str]` |
| `ui_plot_playground_figure` | `Dict` |
| `ui_plot_option_rows` | `DataFrame` |

**Total:** ~200 reactive state variables.

---

## 5. Callback Inventory

### Initialization & Navigation
| Callback | Trigger | Purpose |
|----------|---------|---------|
| `on_init(state)` | App startup | Initialize all state, refresh all pages |
| `on_menu_action(state, id, payload)` | Menu click | Navigate + refresh target page |

### Analyze Text Page
| Callback | Trigger |
|----------|---------|
| `on_qt_analyze(state)` | Detect PII button |
| `on_qt_anonymize(state)` | Anonymize button |
| `on_qt_load_sample(state)` | Load Sample button |
| `on_qt_settings_open(state)` | Settings button |
| `on_qt_settings_close(state)` | Apply/Close in settings dialog |
| `on_qt_clear(state)` | Clear button |
| `on_qt_save_session(state)` | Save Session button |
| `on_qt_load_session(state)` | Load Session button |
| `on_qt_session_select(state, var_name, value)` | Row click in sessions table |
| `on_qt_download_anonymized(state)` | Download .txt button |
| `on_qt_download_entities(state)` | Download .csv button |
| `on_qt_ner_model_change(state, var_name, value)` | NER model selector change |
| `on_spacy_model_change(state, var_name, value)` | spaCy model change |

### Store Settings
| Callback | Trigger |
|----------|---------|
| `on_store_settings_open(state)` | Settings button |
| `on_store_settings_close(state)` | Cancel button |
| `on_store_apply(state)` | Apply button |

### File Upload & Job Submission
| Callback | Trigger |
|----------|---------|
| `on_file_upload(state, action, payload)` | File selector |
| `on_submit_job(state)` | Run Job button |
| `on_poll_progress(state)` | Refresh button |
| `on_job_adv_open(state)` | Advanced Options button |
| `on_job_adv_close(state)` | Close Advanced button |
| `on_download(state)` | Download Results button |

### Job Management
| Callback | Trigger |
|----------|---------|
| `on_select_job(state, var_name, value)` | Job History table row click |
| `on_job_cancel(state)` | Cancel button |
| `on_job_remove(state)` | Remove button |
| `on_whatif_compare(state)` | Compare button |
| `on_promote_primary(state)` | Promote Primary button |

### Pipeline / Kanban
| Callback | Trigger |
|----------|---------|
| `on_card_new(state)` | New Card button |
| `on_card_save(state)` | Save in card form dialog |
| `on_card_cancel(state)` | Cancel in card form dialog |
| `on_card_edit(state)` | Edit Card button |
| `on_card_forward(state)` | Forward ▶ button |
| `on_card_back(state)` | ◀ Back button |
| `on_card_delete(state)` | Delete button |
| `on_attest_open(state)` | Attest button |
| `on_attest_confirm(state)` | Confirm in attestation dialog |
| `on_attest_cancel(state)` | Cancel in attestation dialog |
| `on_card_history(state)` | View History button |
| `on_card_history_close(state)` | Close in history dialog |
| `on_card_pick(state, var_name, value)` | Kanban table row selection |
| `on_pipeline_export_csv(state)` | Export CSV button |
| `on_pipeline_export_json(state)` | Export JSON button |

### Schedule / Appointments
| Callback | Trigger |
|----------|---------|
| `on_appt_new(state)` | New Review button |
| `on_appt_save(state)` | Save in form dialog |
| `on_appt_cancel(state)` | Cancel in form dialog |
| `on_appt_select(state, var_name, value)` | Table row selection |
| `on_appt_edit(state)` | Edit button |
| `on_appt_delete(state)` | Delete button |

### Audit Log
| Callback | Trigger |
|----------|---------|
| `on_audit_filter(state)` | Apply filter button |
| `on_audit_clear(state)` | Clear filter button |
| `on_audit_export_csv(state)` | Export CSV button |
| `on_audit_export_json(state)` | Export JSON button |

### Dashboard
| Callback | Trigger |
|----------|---------|
| `on_refresh_dashboard(state)` | Refresh button |
| `on_dash_filters_change(state, var_name, value)` | Report Mode / Time Window selector change |
| `on_dash_go_analyze(state)` | Navigate to Analyze link |
| `on_dash_seed_demo(state)` | Generate Demo Session button |

### UI Demo
| Callback | Trigger |
|----------|---------|
| `on_ui_demo_filters_change(state, var_name, value)` | Plot control changes |
| `on_ui_demo_refresh(state)` | Refresh button |

### Internal Refresh Functions (called by callbacks, not directly from UI)
| Function | Purpose |
|----------|---------|
| `_refresh_dashboard(state)` | Rebuild all dashboard charts/KPIs |
| `_refresh_pipeline(state)` | Rebuild kanban tables + burndown |
| `_refresh_appts(state)` | Rebuild appointment tables |
| `_refresh_audit(state)` | Rebuild audit log table |
| `_refresh_job_table(state)` | Rebuild job history table |
| `_refresh_ui_demo(state)` | Rebuild all demo figures |
| `_refresh_plotly_playground(state)` | Rebuild playground figure |
| `_refresh_sessions(state)` | Rebuild saved sessions table |

**Total:** ~55 callbacks + ~8 internal refresh functions.

---

## 6. Data Models

All are `@dataclass` in `store/models.py`.

### PIISession
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | `str` | 8-char UUID hex | |
| `title` | `str` | `"Untitled Session"` | |
| `original_text` | `str` | `""` | |
| `anonymized_text` | `str` | `""` | |
| `entities` | `List[Dict]` | `[]` | `{entity_type, start, end, score, text, recognizer, rationale}` |
| `entity_counts` | `Dict[str, int]` | `{}` | e.g. `{PERSON: 3, EMAIL: 1}` |
| `operator` | `str` | `"replace"` | |
| `source_type` | `str` | `"text"` | text / file |
| `file_name` | `Optional[str]` | `None` | |
| `created_at` | `str` | ISO-8601 now | |
| `pipeline_card_id` | `Optional[str]` | `None` | Link to PipelineCard |
| `processing_ms` | `float` | `0.0` | |

### PipelineCard
| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | 8-char UUID hex |
| `title` | `str` | `"New Task"` |
| `description` | `str` | `""` |
| `status` | `str` | `"backlog"` — backlog / in_progress / review / done |
| `card_type` | `str` | `"file"` — file / text / database / api |
| `data_source` | `str` | `""` |
| `assignee` | `str` | `""` |
| `priority` | `str` | `"medium"` — low / medium / high / critical |
| `labels` | `List[str]` | `[]` |
| `session_id` | `Optional[str]` | `None` |
| `created_at` | `str` | ISO-8601 |
| `updated_at` | `str` | ISO-8601 |
| `done_at` | `Optional[str]` | `None` |
| `attestation` | `str` | `""` |
| `attested` | `bool` | `False` |
| `attested_by` | `str` | `""` |
| `attested_at` | `Optional[str]` | `None` |
| `attestation_sig_alg` | `str` | `""` |
| `attestation_sig_key_id` | `str` | `""` |
| `attestation_sig` | `str` | `""` |
| `attestation_sig_public_key` | `str` | `""` |
| `attestation_sig_payload` | `str` | `""` |
| `attestation_sig_payload_hash` | `str` | `""` |
| `attestation_sig_verified` | `bool` | `False` |
| `attestation_sig_error` | `str` | `""` |
| `scenario_id` | `Optional[str]` | `None` |
| `job_id` | `Optional[str]` | `None` |

### Appointment
| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | 8-char UUID hex |
| `title` | `str` | `"PII Review"` |
| `description` | `str` | `""` |
| `scheduled_for` | `str` | `""` — ISO-8601 datetime |
| `duration_mins` | `int` | `30` |
| `attendees` | `List[str]` | `[]` |
| `pipeline_card_id` | `Optional[str]` | `None` |
| `status` | `str` | `"scheduled"` — scheduled / completed / cancelled |
| `created_at` | `str` | ISO-8601 |

### AuditEntry
| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | 8-char UUID hex |
| `timestamp` | `str` | ISO-8601 |
| `actor` | `str` | `"system"` |
| `action` | `str` | `""` — e.g. pii.anonymize, pipeline.move, compliance.attest |
| `resource_type` | `str` | `""` — PIISession, PipelineCard, Appointment |
| `resource_id` | `str` | `""` |
| `details` | `str` | `""` |
| `severity` | `str` | `"info"` — info / warning / critical |

---

## 7. Store API (Data Layer)

Abstract `StoreBase` class in `store/base.py`. All backends (memory, MongoDB, DuckDB) implement these methods.

### Sessions
| Method | Signature | Returns |
|--------|-----------|---------|
| `add_session` | `(session: PIISession)` | `PIISession` |
| `get_session` | `(session_id: str)` | `Optional[PIISession]` |
| `list_sessions` | `()` | `List[PIISession]` (newest first) |
| `list_sessions_by_card` | `(card_id: str)` | `List[PIISession]` |
| `update_session` | `(session_id: str, **kwargs)` | `Optional[PIISession]` |

### Pipeline Cards
| Method | Signature | Returns |
|--------|-----------|---------|
| `add_card` | `(card: PipelineCard)` | `PipelineCard` |
| `update_card` | `(card_id: str, **kwargs)` | `Optional[PipelineCard]` |
| `delete_card` | `(card_id: str)` | `bool` |
| `get_card` | `(card_id: str)` | `Optional[PipelineCard]` |
| `list_cards` | `(status: Optional[str] = None)` | `List[PipelineCard]` |
| `cards_by_status` | `()` | `Dict[str, List[PipelineCard]]` |

### Appointments
| Method | Signature | Returns |
|--------|-----------|---------|
| `add_appointment` | `(appt: Appointment)` | `Appointment` |
| `get_appointment` | `(appt_id: str)` | `Optional[Appointment]` |
| `update_appointment` | `(appt_id: str, **kwargs)` | `Optional[Appointment]` |
| `delete_appointment` | `(appt_id: str)` | `bool` |
| `list_appointments` | `()` | `List[Appointment]` |
| `upcoming_appointments` | `(limit: int = 5)` | `List[Appointment]` |

### Audit Log
| Method | Signature | Returns |
|--------|-----------|---------|
| `list_audit` | `(limit: int = 200)` | `List[AuditEntry]` |
| `log_user_action` | `(actor, action, resource_type, resource_id, details, severity)` | `None` |

### Stats
| Method | Returns |
|--------|---------|
| `stats()` | `Dict` with keys: `total_sessions`, `total_entities_redacted`, `entity_breakdown`, `pipeline_by_status`, `total_appointments`, `total_audit_entries`, `attested_cards` |

### Store Utilities (`store/utils.py`, 17 functions)
| Function | Purpose |
|----------|---------|
| `parse_time_window(window)` | Parse "24h"/"7d"/"30d" to timedelta |
| `is_in_time_window(ts, window)` | Check if timestamp is within window |
| `filter_audit_entries(entries, ...)` | Filter audit by text/severity |
| `count_by_severity(entries)` | Count audit entries by severity |
| `filter_appointments_by_status(appts, status)` | Filter by status |
| `filter_appointments_by_time_range(appts, start, end)` | Filter by time range |
| `get_scheduled_appointments(appts)` | Get future scheduled appointments |
| `filter_cards_by_priority(cards, priority)` | Filter by priority |
| `count_by_priority(cards)` | Count cards by priority |
| `filter_cards_by_status(cards, status)` | Filter by status |
| `filter_cards_attested(cards)` | Filter attested cards |
| `filter_sessions_by_time_window(sessions, window)` | Filter by time window |
| `filter_sessions_by_entities(sessions, entity_types)` | Filter by entity types |
| `count_sessions_by_operator(sessions)` | Count by operator |
| `filter_by_predicate(items, fn)` | Generic filter |
| `group_by(items, key_fn)` | Group items by key |
| `count_by(items, key_fn)` | Count items by key |

---

## 8. PII Engine API

### Entity Types (17)

```
EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN, US_PASSPORT,
US_DRIVER_LICENSE, US_ITIN, US_BANK_NUMBER, IP_ADDRESS, URL,
IBAN_CODE, DATE_TIME, LOCATION, PERSON, NRP, MEDICAL_LICENSE,
ORGANIZATION
```

Plus `CUSTOM_DENYLIST` (generated from user-supplied denylist words).

### Operators

`replace`, `redact`, `mask`, `hash` (core) + `synthesize` (bonus).

### Engine Methods

```python
engine.analyze(
    text: str,
    entities: List[str] = None,       # None = all 17
    threshold: float = 0.35,
    allowlist: Optional[List[str]],    # words to never flag
    denylist: Optional[List[str]],     # words to always flag
) → List[Dict]                        # [{entity_type, start, end, score, text, recognizer, rationale}]

engine.anonymize(
    text: str,
    entities: List[str] = None,
    operator: str = "replace",
    threshold: float = 0.35,
    allowlist: Optional[List[str]],
    denylist: Optional[List[str]],
    fast: bool = False,
) → AnalysisResult
```

### AnalysisResult
| Field | Type |
|-------|------|
| `original_text` | `str` |
| `anonymized_text` | `str` |
| `entities` | `List[Dict]` |
| `entity_counts` | `Dict[str, int]` |
| `operator_used` | `str` |
| `total_found` | `int` (property) |
| `entity_summary` | `str` (property) |

### Display Helpers
| Function | Purpose |
|----------|---------|
| `highlight_md(text, entities)` | Markdown with `\`text\` *(Type · 95%)*` spans |
| `engine.highlight_html(text, entities)` | HTML with `<mark>` tags |
| `ENTITY_COLORS` | `Dict[str, str]` — entity type → hex color |

### Model Management
| Function | Purpose |
|----------|---------|
| `get_engine()` | Singleton PIIEngine getter |
| `get_spacy_model_choice()` | Current model name |
| `get_spacy_model_options()` | All available models |
| `get_spacy_model_status()` | Status string (✓/✗) |
| `set_spacy_model(choice)` | Switch model, returns (name, has_ner, status) |

---

## 9. Services

### 9.1 AppContext (`services/app_context.py`)

Shared mutable runtime state — single `AppContext` dataclass instance in `app.py`:

| Field | Type | Purpose |
|-------|------|---------|
| `scenarios` | `Dict[str, Any]` | job_id → Taipy Scenario |
| `submission_ids` | `Dict[str, str]` | job_id → submission ID |
| `file_cache` | `Dict[str, Dict]` | state_id → uploaded file bytes |
| `burndown_cache` | `Dict[str, Any]` | TTL-cached burndown chart |
| `live_state_ids` | `Set[str]` | Connected GUI state IDs |
| `live_state_lock` | `Lock` | Thread safety |
| `live_stop_event` | `Event` | Stop signal for live thread |
| `live_thread` | `Optional[Thread]` | Background live-push thread |
| `event_processor` | `Any` | Taipy EventProcessor |

### 9.2 Attestation Crypto (`services/attestation_crypto.py`)

Ed25519 digital signatures for compliance attestations.

| Function | Purpose |
|----------|---------|
| `signature_required()` | Check if signatures are mandatory |
| `build_attestation_payload(card, attested_by, ...)` | Build canonical JSON payload |
| `sign_attestation_payload(payload)` | Sign with Ed25519 key → `AttestationSignatureBundle` |
| `verify_attestation_signature(payload_json, sig_b64, pubkey_b64)` | Verify signature |

### 9.3 Synthetic Text (`services/synthetic.py`)

Fake data generation for anonymized placeholders.

| Function | Purpose |
|----------|---------|
| `synthesize_from_anonymized_text(anonymized_text, cfg: SyntheticConfig)` | Replace `<ENTITY>` tags with realistic fake values |

Providers: `faker` (offline), `openai`, `azure_openai` (LLM-based).

### 9.4 Geo Signals (`services/geo_signals.py`)

Location entity resolution for map visualizations.

| Function | Purpose |
|----------|---------|
| `normalize_geo_token(value)` | Normalize location text |
| `resolve_geo_city(value, city_coords, alias_to_city)` | Resolve text to known city |
| `build_geo_place_counts(sessions, ...)` | Aggregate geo mentions for map |

### 9.5 Job Progress (`services/job_progress.py`)

Progress tracking for background jobs (memory + durable JSON snapshots).

| Function | Purpose |
|----------|---------|
| `get_progress_registry()` | Get in-memory progress dict |
| `read_progress(job_id)` | Read freshest progress (memory ∪ snapshot) |
| `persist_progress(job_id, payload)` | Write to memory + snapshot |
| `clear_progress(job_id)` | Remove progress state |

### 9.6 Job Helpers (`services/jobs.py`)

Job submission, file validation, result formatting.

| Function | Purpose |
|----------|---------|
| `new_job_id()` | Generate 12-char UUID |
| `resolve_upload_bytes(state, file_cache, state_id)` | Get uploaded bytes |
| `stage_csv_upload_for_job(job_id, file_name, raw_bytes)` | Persist CSV to temp |
| `parse_upload_to_df(raw_bytes, file_name)` | Parse CSV/Excel → DataFrame |
| `build_job_config(...)` | Build config dict |
| `build_queue_quality_md(...)` | Markdown for queued job |
| `build_result_quality_md(...)` | Markdown for completed job |
| `build_entity_stats_df(stats_data)` | Stats → DataFrame |
| `latest_cancellable_job(jobs)` | Find cancellable job |
| `all_jobs_done_like(jobs)` | Check if all done |

### 9.7 Telemetry (`services/telemetry.py`)

Prometheus metrics for monitoring.

| Metric | Type |
|--------|------|
| `anon_jobs_created_total` | Counter |
| `anon_jobs_status_total` | Counter (label: status) |
| `anon_scenarios_created_total` | Counter |
| `anon_job_duration_seconds` | Histogram |
| `anon_entities_detected_total` | Counter |
| `anon_rows_processed_total` | Counter |
| `anon_job_queue_depth` | Gauge |

### 9.8 Auth0 REST (`services/auth0_rest.py`)

JWT validation middleware for the REST API. Requires `AUTH0_DOMAIN`, `AUTH0_API_AUDIENCE`, `AUTH0_ALGORITHMS` env vars.

### 9.9 Progress Snapshots (`services/progress_snapshots.py`)

Durable JSON-based IPC between worker processes and the GUI process (for `standalone` mode).

### 9.10 Scheduler (`scheduler.py`)

Background daemon thread that polls `schedule.run_pending()` every 30 seconds. When an appointment comes due:
1. Advances linked pipeline card from `in_progress` → `review`.
2. Logs `appointment.due` audit entry.
3. Marks appointment as `completed`.

---

## 10. Background Job Flow

```
User clicks "Run Job"
  → on_submit_job(state)
      → invoke_long_callback(state,
            user_function=_bg_submit_job,
            user_function_args=[raw_df, config],
            user_status_function=_bg_job_done,
            period=5000)

  Background thread (_bg_submit_job):
      → core_config.submit_job(raw_df, config)
          → tc.create_scenario(pii_scenario_cfg)
          → scenario.raw_input.write(df)
          → scenario.job_config.write(config)
          → tc.submit(scenario)
              → run_pii_anonymization(raw_df, job_config)   [Orchestrator thread]
                  → Chunks rows, calls engine.anonymize() per chunk
                  → Writes PROGRESS_REGISTRY[job_id] per chunk
                  → Returns (anonymized_df, stats_dict)

  GUI thread (_bg_job_done):
      → Called periodically (status=int) to poll progress
      → Called on success (status=True) with (scenario_id, job_id, submission_id)
      → Called on failure (status=False) with error
      → Updates state, refreshes tables, sends notifications
```

---

## 11. Taipy Core DataNodes

All `Scope.SCENARIO` (isolated per job).

| DataNode | Type | Contents | Validity |
|----------|------|----------|----------|
| `raw_input` | in-memory / MongoDB / pickle | Uploaded DataFrame | 2 hours |
| `job_config` | pickle | Config dict | 1 day |
| `anon_output` | pickle | Anonymized DataFrame | 14 days |
| `job_stats` | pickle | Stats dict | 14 days |

### Task
- **anonymize_task** — inputs: [raw_input, job_config], outputs: [anon_output, job_stats], function: `run_pii_anonymization`.

### Scenario
- **pii_pipeline** — tasks: [anonymize_task], frequency: WEEKLY, comparators: {job_stats: `_compare_job_stats`}.

---

## 12. CSS & Theming

### Design Tokens (`app.css :root`)
| Token | Value | Purpose |
|-------|-------|---------|
| `--bg0` | `#17191D` | Primary background |
| `--bg1` | `#1D2025` | Secondary background |
| `--bg2` | `#252930` | Tertiary background |
| `--bdr` | `#323841` | Border |
| `--acc` / `--blu` | `#6F86B9` | Accent blue |
| `--grn` | `#79A06F` | Green |
| `--red` | `#D06A64` | Red |
| `--amb` | `#C8A55B` | Amber/yellow |
| `--pur` | `#C58A5A` | Orange/purple |
| `--txt` | `#D7DBE3` | Primary text |
| `--txt2` | `#BCC3CF` | Secondary text |
| `--mut` | `#9199A8` | Muted text |
| `--anon-bg` | `#1A211B` | Anonymized text background |
| `--anon-fg` | `#C4CEC4` | Anonymized text foreground |
| `--anon-tag` | `#7FBF7F` | Anonymized tag color |

### Plotly Theme (`ui/theme.py`)
| Property | Value |
|----------|-------|
| Template | `plotly_dark` |
| Paper BG | `#1D2025` |
| Plot BG | `#17191D` |
| Font | `ui-monospace, monospace`, size 11, color `#D7DBE3` |
| Colorway | `[#D06A64, #C58A5A, #C8A55B, #79A06F, #6F8FA3, #6F86B9, #9BAA66]` |
| Grid | `#323841` |
| Legend | horizontal, below chart |

### Major CSS Class Groups

| Group | Classes | Purpose |
|-------|---------|---------|
| **Layout** | `.pg`, `.page-hd`, `.page-title`, `.page-sub`, `.sh`, `.panel` | Page structure |
| **Dashboard** | `.dash-toolbar`, `.dash-ticker-wrap`, `.dash-ticker-item`, `.dash-kpi`, `.dash-panel` | Dashboard layout |
| **Metrics** | `.mc`, `.mv`, `.ml`, `.mv-blue/purple/green/red/yellow` | KPI cards |
| **Kanban** | `.kc`, `.kh`, `.kh-cnt`, `.kc-gray/purple/yellow/green` | Board columns |
| **Forms** | `.file-ready`, `.file-hash-display`, `.file-hash-art`, `.slider-label` | Input styling |
| **Status** | `.status-ribbon`, `.store-mode-pill`, `.banner-label` | Status indicators |
| **Output** | `.hi-box`, `.anon-box`, `.audit-stmt` | Result display |
| **Schedule** | `.schedule-chip`, `.chip-scheduled/completed/cancelled` | Status chips |
| **Health** | `.health-kpi`, `.health-kpi-v`, `.health-kpi-l` | Health display |
| **Empty State** | `.widget-empty`, `.widget-empty-title/sub/actions` | Placeholder UI |
| **Navigation** | `.taipy-navbar`, `.MuiTab-root`, `.MuiTabs-indicator` | Nav styling |

---

## 13. Assets

### SVG Icons (`images/`)

| File | Used For |
|------|----------|
| `dashboard.svg` | Dashboard menu icon |
| `piitext.svg` | Analyze Text menu icon |
| `jobs.svg` | Batch Jobs menu icon |
| `pipeline.svg` | Pipeline menu icon |
| `schedule.svg` | Schedule menu icon |
| `audit.svg` | Audit Log menu icon |

UI Demo reuses `dashboard.svg`.

---

## 14. Notification Patterns

The app uses `notify(state, severity, message)` with four levels:

| Level | Color | Example Messages |
|-------|-------|-----------------|
| `success` | Green | "Session saved", "Job submitted", "Card updated", "Appointment scheduled", "NLP model switched" |
| `warning` | Amber | "Enter some text first", "Select a card row first", "No results available yet", "Run Anonymize first" |
| `info` | Blue | "Sample medical record loaded", "No active job to poll", "Dashboard refreshed", "Already in Done" |
| `error` | Red | "Job submission failed", "File upload failed", "Download failed", "Invalid upload path rejected", "Title is required" |

~60 notification messages total across all callbacks.

---

## 15. File Upload / Download Flows

### Upload Flow
1. User selects file via `file_selector` (`.csv`, `.xlsx`, `.xls`, max 50 MB).
2. `on_file_upload(state, action, payload)` fires.
3. Path traversal guard validates file is in OS temp directory.
4. Raw bytes stored in `_FILE_CACHE[state_id]` (outside Taipy state — bytes can't be serialized to JSON).
5. SHA-256 computed → `job_file_hash`.
6. Drunken Bishop ASCII art generated → `job_file_art`.
7. `job_file_content` set to filename string (non-None flag).

### Download Flow
1. User clicks download button.
2. `on_download(state)` reads scenario's `anon_output` DataNode.
3. Converts DataFrame to CSV bytes.
4. Calls `download(state, content=csv_bytes, name="anonymized_output.csv")`.

### Text Downloads (Analyze page)
- `on_qt_download_anonymized(state)` — downloads `qt_anonymized_raw` as `.txt`.
- `on_qt_download_entities(state)` — downloads `qt_entity_rows` DataFrame as `.csv`.

---

## 16. Live Dashboard Refresh

A background daemon thread pushes dashboard updates to all connected clients:

1. **Registration:** `_register_live_state(state)` adds session ID to `_LIVE_STATE_IDS` on page load.
2. **Loop:** `_live_dashboard_loop(gui)` runs in a daemon thread, polling every `_DASH_LIVE_POLL_SEC` (~2 seconds).
3. **Push:** For each connected session ID, calls `invoke_callback(gui, sid, _on_live_dashboard_tick)`.
4. **Refresh:** `_on_live_dashboard_tick(state)` calls `_refresh_dashboard(state)` to rebuild KPIs/charts.
5. **Cleanup:** Stale sessions (failed callbacks) are removed from `_LIVE_STATE_IDS`.

---

## 17. Component Inventory Summary

| Category | Count |
|----------|-------|
| Pages | 7 (+ root navigation) |
| Dialogs | 6 |
| Data Tables | 20+ |
| Plotly Charts | 15+ |
| Buttons | 40+ |
| Selectors / Dropdowns | 30+ |
| Text Inputs | 25+ |
| Sliders | 8 |
| Metrics / KPIs | 20+ |
| Multi-Select | 10+ |
| LED Status Indicators | 3 |
| File Selector | 1 |
| Date Picker | 1 |
| Reactive State Variables | ~200 |
| Callbacks | ~55 |
| Internal Refresh Functions | ~8 |
| CSS Custom Rules | ~1018 lines |
| Notification Messages | ~60 |
| SVG Icons | 6 |

### Dropdown/Selector Option Values

| Selector | Options |
|----------|---------|
| Card Status | backlog, in_progress, review, done |
| Card Priority | low, medium, high, critical |
| Card Type | file, text, database, api |
| Appointment Status | scheduled, completed, cancelled |
| Operator | replace, redact, mask, hash (+ synthesize on Analyze page) |
| Audit Severity | all, info, warning, critical |
| Report Mode | All, Operations, Compliance, Throughput |
| Time Window | 24h, 7d, 30d, All |
| Compute Backend | auto, pandas, dask |
| Store Backend | memory, duckdb, mongo |
| Synth Provider | faker, openai, azure_openai |

### Table Column Definitions

| Table | Columns |
|-------|---------|
| Kanban boards | Select, Title, Priority, Job |
| Pipeline All | Title, Priority, Assignee, Job, Labels, Attested, Updated |
| Job History | Job ID, Title, Progress, Status, Entities, Duration, Message |
| Audit Log | Time, Actor, Action, Resource, Details, Severity |
| Appointments | Title, Date/Time, Duration, Attendees, Linked Card, Status |
| Upcoming | Title, Date, Time |
| Entity Evidence (QT) | Entity Type, Text, Confidence, Confidence Band, Span, Recognizer, Rationale |
| Entity Stats (Jobs) | Entity Type, Count |
| Saved Sessions | ID, Title, Operator, Entities, Created |
| Card Sessions | ID, Title, Operator, Entities, Source, Created |
| Card Audit | Time, Action, Actor, Details |
| What-if Compare | Scenario, Processed Rows, Entities, Entities/Row |
| Submissions | Submission, Entity, Status, Jobs, Created |
| Cycles | Cycle, Frequency, Start, End, Scenarios |
