# Taipy Page Index & Navigation Architecture

## Overview

This document provides a comprehensive guide to the page organization, routing, and navigation system in the Anonymous Studio Taipy application.

---

## 1. Page Structure

### 1.1 Page Registry

**File:** `pages/definitions.py:826-835`

All pages are registered in a single dictionary that maps route paths to Markdown content:

```python
PAGES = {
    "/":          NAV,         # Root: Navigation menu
    "dashboard":  DASH,        # Dashboard page
    "analyze":    QT,          # Quick Text (Analyze Text)
    "jobs":       JOBS,        # Batch Jobs
    "pipeline":   PIPELINE,    # Kanban Pipeline
    "schedule":   SCHEDULE,    # Review Scheduling
    "audit":      AUDIT,       # Audit Log
    "ui_demo":    UI_DEMO,     # UI Component Demo
}
```

**Key Points:**
- Each value is a **Markdown string** using Taipy's DSL syntax
- Routes are **case-sensitive** (lowercase preferred)
- Root path `"/"` serves the navigation menu
- All other pages are accessed via their dictionary key

### 1.2 Page Content Format

Pages are defined as **Markdown strings** with Taipy-specific syntax:

```python
# Example from pages/definitions.py
DASH = """
# Dashboard

<|{dashboard_metric}|indicator|>
<|{dashboard_chart}|chart|>
<|{dashboard_table}|table|>
"""
```

**Taipy DSL Elements:**
- `<|{variable}|>` — Display reactive state variable
- `<|{variable}|element_type|prop=value|>` — Interactive control
- `<|part|render={condition}|>` — Conditional rendering
- HTML and Markdown can be mixed freely

---

## 2. Navigation System

### 2.1 Menu Structure

**File:** `app.py:278-288`

The navigation menu is defined as a list of value (LOV) with metadata:

```python
menu_lov = [
    ("dashboard", Icon("images/dashboard.svg", "Dashboard")),
    ("analyze",   Icon("images/piitext.svg",   "Analyze Text")),
    ("jobs",      Icon("images/jobs.svg",      "Batch Jobs")),
    ("pipeline",  Icon("images/pipeline.svg",  "Pipeline")),
    ("schedule",  Icon("images/schedule.svg",  "Reviews")),
    ("audit",     Icon("images/audit.svg",     "Audit Log")),
    ("ui_demo",   Icon("images/dashboard.svg", "UI")),
]
```

**Components:**
- **Value:** Page identifier (matches PAGES dict key)
- **Icon:** SVG file path + display label
- **Order:** Determines menu item sequence

**Rendering:**
```python
NAV = """
<|menu|lov={menu_lov}|on_action=on_menu_action|label=Anonymous Studio|>
"""
```

### 2.2 Navigation Callback

**File:** `app.py:3193-3244`

The `on_menu_action` callback handles all navigation events:

```python
def on_menu_action(state, action, payload):
    """Handle menu selection and page navigation."""
    # Extract selected page
    page = payload["args"][0]  # e.g., "dashboard"
    
    # Normalize (strip "/" prefix, lowercase)
    page = page.lstrip("/").lower()
    
    # Validate page exists
    ALLOWED_PAGES = {
        "dashboard", "analyze", "jobs", 
        "pipeline", "schedule", "audit", "ui_demo"
    }
    if page not in ALLOWED_PAGES:
        notify(state, "error", f"Unknown page: {page}")
        return
    
    # Navigate to page
    navigate(state, page)
    
    # Trigger page-specific refresh
    _refresh_page(state, page)
```

**Key Functions:**
- `navigate(state, page)` — Taipy built-in; switches active page
- `_refresh_page()` — Custom helper to update page-specific state

### 2.3 Page Refresh Logic

**File:** `app.py:3193-3244`

Each page has a dedicated refresh function that updates its state:

```python
def _refresh_page(state, page: str):
    """Refresh page-specific data after navigation."""
    if page == "dashboard":
        _refresh_dashboard(state)
    elif page == "analyze":
        _refresh_sessions(state)
    elif page == "jobs":
        _refresh_job_table(state)
    elif page == "pipeline":
        _refresh_pipeline(state)
    elif page == "schedule":
        _refresh_appts(state)
    elif page == "audit":
        _refresh_audit(state)
    elif page == "ui_demo":
        _refresh_ui_demo(state)
        _refresh_plotly_playground(state)
```

**Purpose:**
- Fetch latest data from store
- Recalculate derived metrics
- Reset page-specific input controls
- Ensure stale data isn't displayed

---

## 3. Page Catalog

### 3.1 Root Page: Navigation Menu (`/`)

**File:** `pages/definitions.py:822-824`

**Content:**
```markdown
<|menu|lov={menu_lov}|on_action=on_menu_action|label=Anonymous Studio|>
```

**Purpose:** Entry point displaying the main navigation menu.

**State Variables:** None (stateless menu).

---

### 3.2 Dashboard (`dashboard`)

**File:** `pages/definitions.py:60-170`

**Purpose:** Real-time operational overview with key metrics and charts.

**Key Sections:**
1. **Hero Metrics** — Total sessions, active jobs, pending reviews, attestations
2. **Pipeline Overview** — Card count by status (backlog/in_progress/review/done)
3. **Upcoming Reviews** — Next 5 scheduled appointments
4. **Burndown Chart** — Pipeline completion trend over time
5. **Recent Activity** — Last 10 audit log entries

**Primary State Variables:**
```python
dash_total_sessions     # Total PIISession count
dash_active_jobs        # Jobs with status=RUNNING
dash_pending_reviews    # Appointments with status=pending
dash_attestation_count  # Cards with attestation!=None
dash_pipeline_overview  # DataFrame: status → count
dash_upcoming_appts     # List of next 5 Appointments
dash_burndown_chart     # Plotly chart data
dash_recent_audit       # Last 10 AuditEntry rows
```

**Refresh Function:** `_refresh_dashboard(state)`

**Auto-Refresh:** Updates every 30s when page is active (via background thread).

---

### 3.3 Analyze Text (`analyze`)

**File:** `pages/definitions.py:614-725`

**Purpose:** Interactive PII detection and anonymization for single text inputs.

**Key Sections:**
1. **Input Panel** — Text area, entity selector, threshold slider, operator dropdown
2. **Control Panel** — Allowlist/denylist inputs, analyze/anonymize buttons
3. **Detection Results** — Color-coded PII highlighting, entity table with confidence scores
4. **Anonymized Output** — Transformed text with entity counts and processing time
5. **Session History** — Table of previous analyses with load/delete actions

**Primary State Variables:**
```python
# Input state
qt_input              # User's text to analyze
qt_entities           # Selected entity types (List[str])
qt_threshold          # Confidence threshold (0.0-1.0)
qt_operator           # Selected operator (replace/redact/mask/hash/synthesize)
qt_allowlist          # Comma-separated whitelist
qt_denylist           # Comma-separated blacklist

# Output state
qt_highlight_md       # Markdown with color-coded PII spans
qt_anonymized         # Anonymized result text
qt_entity_rows        # DataFrame: entity findings
qt_entity_chart       # Plotly bar chart: entity type → count
qt_last_proc_ms       # Processing time in milliseconds
qt_session_rows       # DataFrame: historical sessions
```

**Key Callbacks:**
- `on_qt_analyze(state)` — Detection only (no anonymization)
- `on_qt_anonymize(state)` — Full pipeline (detect + anonymize)
- `on_qt_session_load(state)` — Load historical session into inputs
- `on_qt_session_delete(state)` — Remove session from history

**Refresh Function:** `_refresh_sessions(state)`

---

### 3.4 Batch Jobs (`jobs`)

**File:** `pages/definitions.py:273-432`

**Purpose:** Upload CSV/Excel files for background PII anonymization at scale.

**Key Sections:**
1. **File Upload** — Drag-drop or browse, format validation
2. **Job Configuration** — Operator, entities, threshold, chunk size
3. **Job Queue** — Table of submitted jobs with status and progress
4. **Quality Metrics** — Entity counts, processing duration, error rates
5. **Result Download** — Download anonymized CSV after job completion

**Primary State Variables:**
```python
# Upload state
job_file_content      # Uploaded file (filename string, bytes in AppContext.file_cache)
job_file_format       # Detected format (csv/xlsx)
job_preview_df        # Preview of first 5 rows

# Config state
job_operator          # Selected operator
job_entities          # Selected entity types
job_threshold         # Confidence threshold
job_chunk_size        # Rows per batch (default 100)

# Queue state
job_queue_rows        # DataFrame: all jobs with status/progress/metadata
job_selected_row      # Currently selected job for details/download
job_progress_pct      # Real-time progress (0-100) for active job

# Result state
job_result_df         # Anonymized DataFrame (after job completion)
job_stats_df          # Statistics: entity counts, duration, errors
```

**Key Callbacks:**
- `on_file_upload(state, files)` — Handle file upload and validation
- `on_submit_job(state)` — Queue background job via `invoke_long_callback`
- `on_refresh_progress(state)` — Poll `PROGRESS_REGISTRY` for active jobs
- `on_cancel_job(state)` — Cancel running job via `tc.cancel_job()`
- `on_download_result(state)` — Export anonymized CSV via `download()`

**Refresh Function:** `_refresh_job_table(state)`

**Background Processing:** Jobs execute via Taipy Orchestrator (see `tasks.py:run_pii_anonymization`).

---

### 3.5 Pipeline (`pipeline`)

**File:** `pages/definitions.py:434-611`

**Purpose:** Kanban-style board for managing PII anonymization workflows.

**Key Sections:**
1. **New Card Form** — Title, description, operator, entities, priority
2. **Backlog Column** — Cards waiting to be started
3. **In Progress Column** — Cards actively being processed
4. **Review Column** — Cards pending human review
5. **Done Column** — Completed cards with attestation signatures
6. **Export** — Export all cards as CSV/JSON

**Card Lifecycle:**
```
Backlog → In Progress → Review → Done
   ↑          ↓           ↓        ↓
   └──────────────────────┴────────┘
           (user actions)
```

**Primary State Variables:**
```python
# New card form
card_title_f          # Card title input
card_description_f    # Card description
card_operator_f       # Selected operator
card_entities_f       # Selected entity types
card_priority_f       # Priority (low/medium/high/critical)

# Board state
pipeline_backlog      # List[PipelineCard] with status=backlog
pipeline_in_progress  # List[PipelineCard] with status=in_progress
pipeline_review       # List[PipelineCard] with status=review
pipeline_done         # List[PipelineCard] with status=done
pipeline_all_cards    # DataFrame: all cards with metadata

# Card actions
card_selected_id      # ID of card selected for view/edit/attest
card_attest_operator  # Operator name for attestation signature
```

**Key Callbacks:**
- `on_card_save(state)` — Create new card in backlog
- `on_card_forward(state, card_id)` — Move card to next status
- `on_card_back(state, card_id)` — Move card to previous status
- `on_card_delete(state, card_id)` — Delete card (audit logged)
- `on_card_attest(state, card_id)` — Sign card with Ed25519 attestation
- `on_pipeline_export_csv/json(state)` — Export cards to file

**Refresh Function:** `_refresh_pipeline(state)`

**Integration:** Cards can be linked to Jobs (via `card.job_id` field).

---

### 3.6 Schedule (`schedule`)

**File:** `pages/definitions.py:434-611` (shares definition with pipeline)

**Purpose:** Schedule and manage human review appointments for anonymized datasets.

**Key Sections:**
1. **New Appointment Form** — Title, reviewer, date/time, location, notes
2. **Upcoming Appointments** — Table of pending appointments sorted by date
3. **Past Appointments** — Historical completed appointments
4. **Appointment Actions** — Edit, complete, cancel

**Primary State Variables:**
```python
# New appointment form
appt_title_f          # Appointment title
appt_reviewer_f       # Reviewer name/email
appt_date_f           # Scheduled date (YYYY-MM-DD)
appt_time_f           # Scheduled time (HH:MM)
appt_location_f       # Meeting location (physical/virtual)
appt_notes_f          # Additional notes

# Appointment state
schedule_upcoming     # DataFrame: appointments with status=pending
schedule_past         # DataFrame: appointments with status=completed/cancelled
appt_selected_id      # ID of appointment for view/edit
```

**Key Callbacks:**
- `on_appt_save(state)` — Create new appointment
- `on_appt_complete(state, appt_id)` — Mark appointment as completed
- `on_appt_cancel(state, appt_id)` — Cancel appointment
- `on_appt_delete(state, appt_id)` — Delete appointment (audit logged)

**Refresh Function:** `_refresh_appts(state)`

**Background Scheduler:** `scheduler.py` runs a daemon thread that auto-updates appointment statuses.

---

### 3.7 Audit Log (`audit`)

**File:** `pages/definitions.py:727-818`

**Purpose:** Immutable compliance log of all system actions (GDPR/HIPAA ready).

**Key Sections:**
1. **Filters** — Time window, action type, operator, severity
2. **Audit Table** — All entries with timestamp, operator, action, target, metadata
3. **Export** — Export audit log as CSV/JSON
4. **Statistics** — Action counts, operator activity, severity distribution

**Primary State Variables:**
```python
# Filter state
audit_time_window     # Filter: last_hour/last_day/last_week/last_month/all
audit_action_filter   # Filter: specific action type (e.g., "pii.detect")
audit_operator_filter # Filter: specific operator name
audit_severity_filter # Filter: info/warning/error

# Audit state
audit_rows            # DataFrame: filtered audit entries
audit_stats           # Dict: action_counts, operator_counts, severity_counts
```

**Key Callbacks:**
- `on_audit_filter(state)` — Apply filters and refresh table
- `on_audit_export_csv(state)` — Export audit log to CSV
- `on_audit_export_json(state)` — Export audit log to JSON

**Refresh Function:** `_refresh_audit(state)`

**Data Source:** `store.list_audit()` returns all `AuditEntry` records.

**Audit Events Generated:**
- `pii.detect` — PII detection performed
- `pii.anonymize` — Text anonymized
- `job.submit` — Batch job submitted
- `job.complete` — Batch job completed
- `card.create` — Pipeline card created
- `card.update` — Pipeline card updated
- `card.delete` — Pipeline card deleted
- `card.attest` — Pipeline card attested
- `schedule.create` — Appointment created
- `schedule.update` — Appointment updated
- `schedule.delete` — Appointment deleted
- `session.create` — Text analysis session saved
- `session.update` — Session updated
- `session.delete` — Session deleted

---

### 3.8 UI Demo (`ui_demo`)

**File:** `pages/definitions.py:820-818` (not fully shown in snippet)

**Purpose:** Demo page showcasing Taipy UI components (development/testing).

**Key Sections:**
1. **Component Gallery** — All Taipy controls with examples
2. **Plotly Playground** — Interactive chart builder
3. **Style Testing** — Theme and CSS overrides

**Primary State Variables:**
```python
ui_demo_text          # Text input demo
ui_demo_number        # Number input demo
ui_demo_slider        # Slider demo
ui_demo_toggle        # Toggle demo
ui_demo_selector      # Selector demo
ui_demo_date          # Date picker demo
ui_demo_chart_data    # Chart data for playground
```

**Refresh Function:** `_refresh_ui_demo(state)`, `_refresh_plotly_playground(state)`

**Note:** This page is typically hidden in production (remove from `menu_lov`).

---

## 4. Navigation Patterns

### 4.1 Direct Navigation

**From Code:**
```python
# Navigate to specific page
navigate(state, "dashboard")
navigate(state, "jobs")

# Redirect in callback
def on_submit_job(state):
    # Submit job...
    navigate(state, "pipeline")  # Redirect to pipeline after submission
```

**From UI:**
```markdown
<|Go to Jobs|button|on_action=lambda s: navigate(s, "jobs")|>
```

### 4.2 Conditional Navigation

**Example: Redirect if unauthorized**
```python
def on_navigate(state, page_name) -> str:
    """Global navigation interceptor."""
    if page_name in {"pipeline", "audit"} and not state.is_admin:
        notify(state, "error", "Admin access required")
        return "dashboard"  # Redirect to dashboard
    return page_name  # Allow navigation
```

### 4.3 Navigation with State Preservation

**Example: Edit → Save → Return**
```python
def on_card_edit(state, card_id):
    # Store return page
    state._return_page = state.active_page
    
    # Load card into edit form
    card = store.get_card(card_id)
    state.card_edit_id = card.id
    state.card_edit_title = card.title
    
    # Navigate to edit page
    navigate(state, "pipeline_edit")

def on_card_save_edit(state):
    # Save changes...
    
    # Return to previous page
    navigate(state, state._return_page or "pipeline")
```

---

## 5. Page Lifecycle

### 5.1 Page Load Sequence

```
1. User clicks menu item
   ↓
2. on_menu_action(state, action, payload) called
   ↓
3. validate page exists
   ↓
4. navigate(state, page) — Taipy switches page
   ↓
5. _refresh_page(state, page) — Fetch fresh data
   ↓
6. State updates propagate to UI
   ↓
7. Page renders with updated state
```

### 5.2 State Initialization

**Global State (app.py module-level vars):**
- Initialized once at app startup
- Persist across page navigation
- Shared across all pages

**Page-Local State:**
- Reset on each page navigation via `_refresh_*()` functions
- Examples: form inputs, filter selections, selected row IDs

**Example:**
```python
# Global state (persists)
current_user = "operator@example.com"
session_id = _uid()

# Page-local state (resets on navigation)
job_file_content = None
job_selected_row = None
```

### 5.3 State Cleanup

**On Navigation Away:**
```python
def _refresh_jobs(state):
    """Reset jobs page state."""
    state.job_file_content = None
    state.job_preview_df = None
    state.job_selected_row = None
    # ... clear other page-local state
```

---

## 6. Advanced Navigation Features

### 6.1 Breadcrumb Navigation

**Not implemented by default**, but can be added:

```python
breadcrumb_trail = [("Home", "/"), ("Dashboard", "dashboard")]

def on_menu_action(state, action, payload):
    page = payload["args"][0]
    navigate(state, page)
    
    # Update breadcrumb
    state.breadcrumb_trail.append((page.title(), page))
```

### 6.2 Back/Forward Navigation

**Not implemented by default** (Taipy doesn't expose browser history API).

**Workaround:** Manual history stack:
```python
nav_history = []

def navigate_with_history(state, page):
    state.nav_history.append(state.active_page)
    navigate(state, page)

def navigate_back(state):
    if state.nav_history:
        prev_page = state.nav_history.pop()
        navigate(state, prev_page)
```

### 6.3 Deep Linking with Query Parameters

**Not supported by Taipy core**, but can be simulated:

```python
# Manual query param parsing
def on_navigate(state, page_name) -> str:
    if "?" in page_name:
        page, query = page_name.split("?", 1)
        params = dict(p.split("=") for p in query.split("&"))
        
        # Use params
        if "job_id" in params:
            state.job_selected_id = params["job_id"]
        
        return page
    return page_name
```

---

## 7. Page Performance Optimization

### 7.1 Lazy Loading Data

```python
def _refresh_dashboard(state):
    """Only load data for visible sections."""
    # Always load hero metrics (fast)
    state.dash_total_sessions = len(store.list_sessions())
    
    # Conditionally load heavy charts
    if state.dash_show_burndown:
        state.dash_burndown_chart = _build_burndown_chart()
```

### 7.2 Caching

```python
# Cache expensive computations
_dashboard_cache = {}

def _refresh_dashboard(state):
    cache_key = f"{len(store.list_sessions())}_{len(store.list_cards())}"
    
    if cache_key in _dashboard_cache:
        state.dash_pipeline_overview = _dashboard_cache[cache_key]
    else:
        data = _compute_pipeline_overview()
        _dashboard_cache[cache_key] = data
        state.dash_pipeline_overview = data
```

### 7.3 Partial Updates

```python
# Only refresh changed sections
def on_card_status_change(state, card_id):
    # Don't refresh entire page, just update affected column
    card = store.get_card(card_id)
    
    if card.status == "in_progress":
        state.pipeline_in_progress = store.cards_by_status("in_progress")
    elif card.status == "review":
        state.pipeline_review = store.cards_by_status("review")
```

---

## 8. Page Testing

### 8.1 Unit Testing Pages

**File:** `tests/test_taipy_mockstate_smoke.py`

```python
from unittest.mock import MagicMock

def test_dashboard_refresh():
    """Test dashboard refresh updates all state variables."""
    state = MagicMock()
    
    _refresh_dashboard(state)
    
    assert state.dash_total_sessions is not None
    assert state.dash_active_jobs is not None
    assert state.dash_pipeline_overview is not None
```

### 8.2 Integration Testing Navigation

```python
def test_menu_navigation():
    """Test navigation from menu."""
    state = MagicMock()
    payload = {"args": ["dashboard"]}
    
    with patch("app.navigate") as mock_navigate:
        on_menu_action(state, "menu_action", payload)
        mock_navigate.assert_called_once_with(state, "dashboard")
```

### 8.3 End-to-End Testing

**Manual testing checklist:**
- [ ] All menu items navigate to correct pages
- [ ] Page refresh functions load expected data
- [ ] State persists across navigation (global vars)
- [ ] State resets correctly on return (page-local vars)
- [ ] No errors in browser console
- [ ] Performance: pages load <1s on typical hardware

---

## 9. Common Patterns

### 9.1 Form-Submit-Redirect

```python
def on_form_submit(state):
    # Validate
    if not state.form_title:
        notify(state, "error", "Title required")
        return
    
    # Save
    entity = store.create_entity(state.form_title, ...)
    
    # Clear form
    state.form_title = ""
    
    # Redirect
    navigate(state, "success_page")
    
    # Notify
    notify(state, "success", f"Saved: {entity.title}")
```

### 9.2 List-Detail-Edit

```python
# List page
def on_item_select(state, item_id):
    state.selected_item_id = item_id
    navigate(state, "detail")

# Detail page
def on_edit_click(state):
    item = store.get_item(state.selected_item_id)
    state.edit_form_title = item.title
    navigate(state, "edit")

# Edit page
def on_save_click(state):
    store.update_item(state.selected_item_id, title=state.edit_form_title)
    navigate(state, "detail")
```

### 9.3 Wizard/Multi-Step Form

```python
wizard_step = 1

def on_wizard_next(state):
    if state.wizard_step == 1 and not _validate_step1(state):
        return
    
    state.wizard_step += 1
    
    if state.wizard_step > 3:
        _submit_wizard(state)
        navigate(state, "success")

def on_wizard_back(state):
    state.wizard_step = max(1, state.wizard_step - 1)
```

---

## 10. Troubleshooting

### Issue: Page not rendering

**Causes:**
1. Missing from `PAGES` dict
2. Syntax error in Markdown string
3. Undefined state variable referenced

**Debug:**
```python
# Check page is registered
print("dashboard" in PAGES)  # Should be True

# Validate Markdown syntax
from taipy.gui.builder import get_page
page = get_page(DASH)  # Will raise exception if syntax error
```

### Issue: State not updating after navigation

**Cause:** Forgot to call `_refresh_*()` function after navigation.

**Fix:**
```python
def on_menu_action(state, action, payload):
    page = payload["args"][0]
    navigate(state, page)
    _refresh_page(state, page)  # ← Add this
```

### Issue: Navigation loop

**Cause:** `on_navigate` returns different page than requested, causing infinite redirect.

**Fix:**
```python
def on_navigate(state, page_name) -> str:
    # Always return a valid page name
    if page_name not in PAGES:
        return "dashboard"  # Default fallback
    return page_name
```

---

## 11. Best Practices

### 11.1 Page Organization

✅ **Do:**
- One page definition per file (or logical grouping)
- Clear section comments in Markdown strings
- Consistent naming: `{page}_*` for page-specific state

❌ **Don't:**
- Mix multiple unrelated pages in one string
- Use generic variable names like `input1`, `output2`
- Create circular navigation dependencies

### 11.2 State Management

✅ **Do:**
- Reset page-local state in `_refresh_*()` functions
- Use descriptive variable names (e.g., `job_file_content` not `file`)
- Document which variables are global vs page-local

❌ **Don't:**
- Pollute global state with page-local variables
- Forget to clear form inputs after submission
- Store large objects (>100MB) in state

### 11.3 Navigation Logic

✅ **Do:**
- Validate page names before calling `navigate()`
- Show notifications on navigation errors
- Log navigation events for debugging

❌ **Don't:**
- Call `navigate()` inside `on_navigate()` (infinite loop)
- Navigate without user action (confusing UX)
- Skip refresh functions after navigation

---

## 12. Reference

### Key Files
- `pages/definitions.py` — All page Markdown strings
- `app.py` — Navigation callbacks & state management
- `main.py` — App entry point (registers pages)

### Related Documentation
- `docs/presidio-taipy-integration.md` — Presidio integration details
- `.github/copilot-instructions.md` — Full codebase conventions
- Taipy Docs: https://docs.taipy.io/

### State Variable Naming Convention

| Prefix | Example | Purpose |
|--------|---------|---------|
| `dash_*` | `dash_total_sessions` | Dashboard page state |
| `qt_*` | `qt_input` | Quick Text (Analyze) page state |
| `job_*` | `job_queue_rows` | Batch Jobs page state |
| `card_*` | `card_title_f` | Pipeline card form state |
| `appt_*` | `appt_date_f` | Appointment form state |
| `audit_*` | `audit_rows` | Audit log page state |
| `*_f` | `card_title_f` | Form input variable |
| `*_rows` | `job_queue_rows` | Table data (DataFrame) |
| `*_chart` | `dash_burndown_chart` | Chart data (Plotly) |

---

## 13. Summary

**Page Architecture:**
- **7 main pages** registered in `PAGES` dict
- **Markdown DSL** for page content with reactive state binding
- **Menu-driven navigation** via `on_menu_action` callback
- **Page-specific refresh** functions for data loading

**Navigation Flow:**
```
Menu Click → Validate → navigate() → Refresh State → Render
```

**Key Design Principles:**
1. **Declarative UI** — Pages defined as Markdown strings
2. **Reactive State** — Automatic UI updates when state changes
3. **Centralized Routing** — All navigation through single callback
4. **Per-Page Refresh** — Each page controls its own data loading

---

*Last Updated: 2026-03-06*  
*Version: 1.0*  
*Status: Complete Reference*
