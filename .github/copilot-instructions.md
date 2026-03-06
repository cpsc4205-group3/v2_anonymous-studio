# Anonymous Studio — Copilot Instructions

This is **v2** — a full rewrite of the PoC ([cpsc4205-group3/anonymous-studio](https://github.com/cpsc4205-group3/anonymous-studio)) that replaces Streamlit with **Taipy GUI + taipy.core** for non-blocking background job execution.

## Running the App

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # optional but recommended
python app.py
# → http://localhost:5000
```

**Requires Python 3.10–3.13.** Python 3.14 is not supported (Presidio/spaCy have no wheels for it).

### Production mode
```bash
export ANON_MODE=standalone
export ANON_WORKERS=4
python app.py
```

### Linting
```bash
flake8 . --max-line-length=120
```
Max line length is **120**. There are no automated tests in this repo yet — the PoC test suite (`test_streamlit.py`) does not apply here.

---

## Branching & PR Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready — PRs only, no direct pushes |
| `feature/<short-name>` | New features |
| `bugfix/<short-name>` | Bug fixes |
| `docs/<short-name>` | Documentation only |

PRs require 1 approving review and all status checks passing. Prefer *Squash and merge*.

---

## Architecture

Five-file Python app. No web framework — all UI is **Taipy GUI** (Markdown DSL with reactive state).

| File | Role |
|------|------|
| `app.py` | All Taipy GUI pages, state variables, and callbacks (~1200 lines) |
| `core_config.py` | taipy.core DataNodes, Task, Scenario, Orchestrator bootstrap |
| `tasks.py` | `run_pii_anonymization()` — the function the Orchestrator executes |
| `pii_engine.py` | Presidio Analyzer + Anonymizer wrapper; spaCy model resolution |
| `store.py` | In-memory store for Kanban cards, appointments, audit log |

### Background job flow

```
on_submit_job() in app.py
  → invoke_long_callback(_bg_submit_job)   ← keeps UI non-blocking
      → cc.submit_job(df, config)           ← core_config.py
          → tc.create_scenario(pii_scenario_cfg)
          → scenario.raw_input.write(df)
          → scenario.job_config.write(config)
          → tc.submit(scenario)
              → run_pii_anonymization()     ← tasks.py, Orchestrator thread
                  writes PROGRESS_REGISTRY[job_id] per chunk
                  returns (anonymized_df, stats) → output DataNodes
  ← _bg_job_done(state, status, result)    ← GUI thread, updates card + table
```

The GUI polls `PROGRESS_REGISTRY` (in-process dict) when the user clicks "Refresh Progress". On completion, the linked Kanban card auto-advances to `review`.

### taipy.core DataNodes (all `Scope.SCENARIO` — isolated per job)

| DataNode | Contents |
|----------|----------|
| `raw_input` | Uploaded DataFrame |
| `job_config` | `{job_id, operator, entities, threshold, chunk_size}` |
| `anon_output` | Anonymized DataFrame |
| `job_stats` | `{total_entities, entity_counts, duration_s, errors, sample_before, sample_after}` |

---

## Key Conventions

### Taipy GUI state
All module-level variables in `app.py` are reactive state bound by name in the Markdown DSL (`<|{variable}|>`). Update state inside callbacks with `state.variable = value`. Never shadow a state variable with a local of the same name inside a callback. Use `notify(state, "success"|"warning"|"error"|"info", "message")` for toasts.

### File upload — bytes live outside state
Taipy serializes state to JSON, so raw bytes can't be stored in a state variable. `on_file_upload` writes to the module-level `_FILE_CACHE = {"bytes": None, "name": ""}` dict. `state.job_file_content` holds only the filename string as a non-None flag.

### `invoke_long_callback` signature
```python
invoke_long_callback(
    state,
    user_function=_bg_submit_job,               # runs in background thread — no state access
    user_function_args=[None, raw_df, config],  # passed verbatim as positional args
    user_status_function=_bg_job_done,          # called on GUI thread when done/periodic
    period=0,                                   # ms between periodic status calls; <500 = off
)
```
**Critical:** the background function does NOT receive `state` — Taipy does not inject it. All args are passed exactly as given in `user_function_args`. In the app, `None` is the first arg because `_bg_submit_job(state_id, raw_df, config)` accepts but ignores `state_id`. If the background function needs to call back into the GUI mid-run (not just on completion), pass `get_state_id(state)` and the `gui` object explicitly, then use `invoke_callback(gui, state_id, fn)`.

Status function signature: `(state, status_or_count, *user_status_function_args, function_result)` where `status_or_count` is `True` on success, `False` on exception, or an `int` period count. The background function's **return value** is `function_result`.

### `store.py` public interface is a stable contract
`app.py` calls only these methods — change internals freely, keep signatures stable:
`add_card`, `update_card`, `delete_card`, `get_card`, `list_cards`, `cards_by_status`, `add_appointment`, `update_appointment`, `delete_appointment`, `list_appointments`, `upcoming_appointments`, `add_session`, `list_audit`, `log_user_action`, `stats`

**Known store.py bugs (as of Sprint 3-1):**
- `app.py` calls `store.list_appts()` and `store.upcoming_appts()` in some refresh helpers — the correct names are `list_appointments()` / `upcoming_appointments()`. These fail silently because refresh helpers catch all exceptions.
- `on_appt_edit` accesses `store._appointments` directly (internal) because `store.get_appointment(id)` does not exist as a public method. Add `get_appointment(id)` to the public interface when implementing the edit form.
- `update_appointment` and `delete_appointment` leave no audit trail.

### spaCy model resolution
`pii_engine.py::_find_spacy_model()` tries in order: `$SPACY_MODEL` env var → `en_core_web_lg` → `md` → `sm` → `trf` → blank fallback. The blank fallback is intentional for offline/restricted environments. To override, set `SPACY_MODEL` or run `python -m spacy download <name>` and restart.

### config.toml is documentation only
`core_config.py` registers all DataNodes/Tasks/Scenarios programmatically. `config.toml` exists only for the Taipy Studio VS Code extension — it is **not loaded at runtime** because Taipy 4.x doesn't auto-convert TOML scope strings to `Scope` enums.

### MongoDB swap
`store.py` is structured for a drop-in MongoDB backend. Replace `DataStore` internals using the pattern from the PoC (`mongo_persistence.py` in `cpsc4205-group3/anonymous-studio`): read `MONGODB_URI` from env, use `python-dotenv`, cache the client with `@lru_cache`. The database name defaults to `anonymous_studio` via `MONGODB_DB_NAME` env var. Nothing in `app.py` changes — it only calls the public `store.*` methods.

### Security
- **Never log raw user text** — it contains PII.
- All credentials (`MONGODB_URI`, `AZURE_*`, etc.) must come from environment variables or `.env` — never hard-coded.
- `.env` is gitignored; add it to `.gitignore` if not present.

---

## What NOT to Change Without Good Reason

- **`invoke_long_callback` in `on_submit_job()`** — replacing with a direct `tc.submit()` call will block the UI thread.
- **`Scope.SCENARIO` on all DataNodes** — changing to `GLOBAL` makes concurrent jobs overwrite each other's data.
- **`_find_spacy_model()` resolution order** — the blank fallback at the end is required for restricted/offline environments.

---

## Known Limitations

- **Kanban is rendered as tables** — Taipy has no native Kanban widget. Cards are table rows; users move them with Forward/Back buttons. Intentional, not a bug.
- **`PROGRESS_REGISTRY` is in-process** — in `standalone` mode (separate worker subprocesses), the dict is invisible to the GUI process. Real-time progress in production requires Redis or polling the `job_stats` DataNode.
- **In-memory store resets on restart** — all pipeline cards, appointments, and audit entries are lost. See MongoDB swap above.
- **No authentication** — suitable for course demo; needs a proxy or middleware before real deployment.

---

## Design Tokens

| Token | Value |
|-------|-------|
| Background | `#0E1117` |
| Secondary bg | `#262730` |
| Card bg | `#1E2335` |
| Border | `#272D3E` |
| Primary (red) | `#FF2B2B` |
| Accent (purple) | `#8A38F5` |
| Text | `#F0F2F8` |
| Muted | `#7A819A` |
| Fonts | Syne (headings), IBM Plex Mono (code/output) |

---

## Taipy Reference

> Sourced from https://github.com/Avaiga/taipy-doc — concepts most relevant to this project.

---

### GUI — Markdown DSL Syntax

Every visual element uses `<|...|element_type|prop=value|>` syntax in page strings.

```
<|{variable}|>                          # display text (default: text element)
<|{variable}|input|>                    # editable text input
<|{variable}|slider|min=0|max=100|>     # slider
<|Label|button|on_action=my_callback|>  # button
<|{df}|table|>                          # table from DataFrame
<|{df}|chart|x=col1|y=col2|>           # chart
<|{flag}|toggle|>                       # toggle (bool)
<|{value}|selector|lov={options}|>      # dropdown/selector
<|{open}|dialog|title=My Dialog|        # dialog block
content
|>
```

**Property shorthand:** The first fragment is always the *default property* of that element type (usually `value`). These are equivalent:
```
<|{x}|slider|>
<|{x}|slider|value={x}|>
```

**Expressions work inline:**
```
<|{x * 2:.2f}|>       # formatted expression
<|{len(items)}|>      # function call
```

**In Python Builder API** (`import taipy.gui.builder as tgb`), variables must use string f-syntax to create reactive bindings:
```python
tgb.slider("{value}")          # ✅ reactive binding — updates when value changes
tgb.slider(value=my_var)       # ❌ sets once at definition time, never updates
```

---

### GUI — State & Variable Binding

- Every module-level variable in the file where `Gui()` is created is **reactive state**.
- Callbacks receive a `State` object. Read and write variables through it: `state.x = 42`.
- The `State` object is **per-user** — in a multi-user deployment each connection gets its own state.
- **Never assign complex mutable objects and expect automatic re-render.** After mutating a list/dict in place, call `state.refresh("variable_name")` to propagate the change to the frontend.
- To update state from a lambda (where assignment is forbidden), use `state.assign("var", value)`.

**Variable lookup order:** Taipy first searches the module where the page is defined, then falls back to `__main__`. Pages defined in separate modules can bind to their own local variables.

---

### GUI — Callback Signatures

| Callback | When called | Signature |
|----------|-------------|-----------|
| `on_init(state)` | New browser connection | `(state)` |
| `on_change(state, var_name, var_value)` | Any bound variable changes | `(state, name, value)` |
| `on_action(state, id)` | Button pressed / action triggered | `(state, id)` |
| `on_navigate(state, page_name) -> str` | User navigates to a page | return page name to redirect |
| `on_exception(state, function_name, ex)` | Unhandled exception in a callback | `(state, fn_name, ex)` |

**Control-specific callbacks** override the global one. Preferred pattern for large apps:
```
<|{value}|slider|on_change=on_slider_change|>
```
The per-control callback only receives `state` (not `var_name`/`var_value`) since the variable is already known.

---

### GUI — Long-Running Callbacks (`invoke_long_callback`)

Use when a callback would take more than a fraction of a second. Keeps the UI responsive.

```python
from taipy.gui import invoke_long_callback

def background_fn(state_id, arg1, arg2):
    # Runs in a background thread — DO NOT access state here
    result = do_heavy_work(arg1, arg2)
    return result                   # returned to status_fn as `result`

def on_done(state, status, result):
    # Runs back on the GUI thread — CAN access state
    # status: True = success, False = error; or int = period tick count
    state.output = result
    notify(state, "success", "Done!")

def on_action(state):
    invoke_long_callback(
        state,
        user_function=background_fn,
        user_function_args=[None, arg1, arg2],  # None = state_id placeholder
        user_status_function=on_done,
        period=5000,   # optional: call status_fn every 5s while running
    )
```

**Alternatively**, manage threads manually with `invoke_callback(gui, state_id, fn)` to call back into the GUI thread from any thread:
```python
from taipy.gui import get_state_id, invoke_callback

def thread_fn(state_id, gui):
    do_work()
    invoke_callback(gui, state_id, update_ui_fn)

def on_action(state):
    Thread(target=thread_fn, args=[get_state_id(state), gui]).start()
```

---

### GUI — Notifications

```python
from taipy.gui import notify

notify(state, "success", "Saved!")
notify(state, "warning", "Check inputs.")
notify(state, "error",   "Job failed.")
notify(state, "info",    "Processing…")

# Permanent (stays until user closes):
notify(state, "info", "Long task running…", duration=0, id="job_notif")

# Close programmatically:
from taipy.gui import close_notification
close_notification(state, id="job_notif")
```

---

### GUI — Pages & Multi-Page Apps

Register multiple pages by passing a dict to `Gui`:
```python
Gui(pages={
    "/":          root_page,
    "dashboard":  dash_page,
    "jobs":       jobs_page,
}).run()
```

Page content can be:
- A **Markdown string** — most common, used in this project
- A **`tgb.Page()` builder block**
- An **HTML string**

Pages defined in separate modules can bind to their own local variables. Variables in `__main__` are accessible from any page without importing.

**Navigate between pages** by changing `state.active_page` or calling `navigate(state, "page_name")`. Use `on_navigate` to intercept navigation and redirect.

---

### taipy.core — Config vs Entity (Critical Distinction)

| Concept | Object | Created by | When |
|---------|--------|-----------|------|
| **Config** | `DataNodeConfig`, `TaskConfig`, `ScenarioConfig` | Developer via `Config.configure_*()` | App startup / import time |
| **Entity** | `DataNode`, `Task`, `Scenario`, `Job` | Taipy at runtime via `tc.create_scenario()` etc. | Each run |

One config can generate many entities. Configs describe *how*; entities are *instances* of that description.

**After the Orchestrator is started, configs are locked** — no more `Config.configure_*()` calls.

---

### taipy.core — Scenario Lifecycle

```python
import taipy.core as tc
from taipy import Config

# 1. Configure (once, at import time)
dn_cfg   = Config.configure_pickle_data_node("my_dn", scope=Scope.SCENARIO)
task_cfg = Config.configure_task("my_task", function=my_fn, input=[dn_cfg], output=[...])
sc_cfg   = Config.configure_scenario("my_scenario", task_configs=[task_cfg])

# 2. Create entity (each job run)
sc = tc.create_scenario(sc_cfg)

# 3. Write inputs
sc.my_dn.write(some_data)

# 4. Submit
submission = tc.submit(sc)

# 5. Read outputs (after completion)
result = sc.output_dn.read()
```

---

### taipy.core — Scope

`Scope` controls how many scenario instances share a DataNode instance.

| Scope | DataNode is shared across… | Use case |
|-------|---------------------------|----------|
| `Scope.SCENARIO` | Only the scenario it was created with | ✅ Isolated per-job data (used in this project) |
| `Scope.CYCLE` | All scenarios in the same time cycle | Shared reference data per time period |
| `Scope.GLOBAL` | All scenarios of the same config | Shared lookup tables, model weights |

**This project uses `Scope.SCENARIO` on all DataNodes.** Never change this to `GLOBAL` — concurrent jobs would overwrite each other's inputs/outputs.

---

### taipy.core — Job Status Lifecycle

```
SUBMITTED → PENDING → RUNNING → COMPLETED
                 ↘ BLOCKED (input deps not ready) → PENDING → RUNNING
                                                              ↘ FAILED
         → CANCELED (by user, before RUNNING)
         → ABANDONED (downstream of a cancelled job)
         → SKIPPED (task marked skippable + inputs unchanged)
```

Access status: `job.status` — compare to `from taipy.core import Status`:
```python
from taipy.core import Status
if job.status == Status.COMPLETED: ...
if job.status == Status.FAILED:    print(job.stacktrace)
if job.status == Status.RUNNING:   ...
```

**Get jobs:**
```python
tc.get_jobs()                    # all jobs ever created
tc.get_latest_job(task)          # latest job for a specific task
tc.get(job_id)                   # by id
```

**Cancel a job** (only when SUBMITTED / PENDING / BLOCKED):
```python
tc.cancel_job(job)
```

---

### taipy.core — Subscribing to Job Status Changes

```python
def on_job_status_change(scenario, job):
    print(f"Job {job.id} status: {job.status}")

tc.subscribe_scenario(on_job_status_change)              # all scenarios
tc.subscribe_scenario(on_job_status_change, my_scenario) # specific scenario
tc.unsubscribe_scenario(on_job_status_change)
```

This is an alternative to polling `PROGRESS_REGISTRY`. In `standalone` mode (separate worker processes), subscriptions persist across process boundaries — but `PROGRESS_REGISTRY` does not.

---

### taipy.core — DataNode Read/Write

```python
sc.my_data_node.write(value)   # write any Python object
value = sc.my_data_node.read() # read it back
```

Pickle DataNodes serialize arbitrary Python objects. The file is stored at the path configured in `ANON_STORAGE` (default `/tmp/anon_studio`).

---

### taipy.core — Execution Modes

Configured via `Config.configure_job_executions()` before starting the Orchestrator:

```python
# Development (default) — synchronous, single process
Config.configure_job_executions(mode="development")

# Standalone — true parallel subprocesses
Config.configure_job_executions(mode="standalone", max_nb_of_workers=4)
```

In `development` mode, `tc.submit()` executes the task synchronously in the same process. In `standalone` mode, the Orchestrator spawns worker subprocesses — `PROGRESS_REGISTRY` (an in-process dict) will not be visible to the GUI process.

---

### GUI — Styling

Every Taipy visual element generates an HTML element with a CSS class `taipy-<element_type>` (e.g. `taipy-button`, `taipy-table`). Add custom CSS via a `.css` file placed next to the app or passed to `Gui(..., css_file="style.css")`.

Add extra classes to any element with `class_name`:
```
<|Label|button|class_name=my-btn|>
```

Pass many properties cleanly via a dict with `properties`:
```python
props = {"title": "My Dialog", "labels": "Cancel;OK"}
# <|{open}|dialog|properties=props|>
```


---

## Presidio Reference

> Sourced from https://microsoft.github.io/presidio/ — the upstream library this project wraps.

---

### Architecture

```
AnalyzerEngine
  ├── NlpEngine (spaCy model — provides tokens/lemmas for ML-based entities)
  ├── RecognizerRegistry (all PII recognizers)
  └── ContextAwareEnhancer (boosts score when context words appear near PII)

AnonymizerEngine
  └── Operators: replace, redact, mask, hash, encrypt, keep, custom
```

`pii_engine.py` wraps both engines. `AnalyzerEngine` → `AnonymizerEngine` is the two-step flow.

---

### Entity Detection Methods

Entities split into two families — important because the blank spaCy fallback breaks ML-based ones:

| Method | Entities | Requires NLP model |
|--------|----------|--------------------|
| Pattern match / regex / checksum | `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `US_SSN`, `US_PASSPORT`, `US_DRIVER_LICENSE`, `US_ITIN`, `US_BANK_NUMBER`, `IP_ADDRESS`, `URL`, `IBAN_CODE`, `DATE_TIME`, `MEDICAL_LICENSE` | ❌ No |
| Custom logic + NLP context | `PERSON`, `LOCATION`, `NRP` | ✅ Yes — blank fallback skips these |

**Conclusion:** without `en_core_web_lg` installed, the 3 ML-dependent entities are silently skipped. The model status banner in the UI surfaces this.

---

### Additional Entities Presidio Supports (not yet in the app)

The app's 16 entities are a subset. Presidio also supports: `CRYPTO` (Bitcoin), `MAC_ADDRESS`, `UK_NHS`, `UK_NINO`, `ES_NIF`, `ES_NIE`, `IT_FISCAL_CODE`, `IN_AADHAAR`, `IN_PAN`, `AU_TFN`, and many more. To add them: append to `ALL_ENTITIES` in `pii_engine.py`.

---

### Analyzer — Key Parameters

```python
results = analyzer.analyze(
    text="...",
    entities=["PERSON", "EMAIL_ADDRESS"],   # subset of ALL_ENTITIES, or omit for all
    language="en",
    score_threshold=0.35,                   # min confidence (0–1); app default is 0.35
    return_decision_process=True,           # attaches explanation to each RecognizerResult
)
```

`return_decision_process=True` enables the **Detection Rationale** feature (project board item). Each `RecognizerResult` then has an `.analysis_explanation` attribute describing why that span was matched.

---

### Anonymizer — Operator Config

```python
from presidio_anonymizer.entities import OperatorConfig

operators = {
    "PERSON":        OperatorConfig("replace", {"new_value": "<PERSON>"}),
    "EMAIL_ADDRESS": OperatorConfig("redact",  {}),
    "CREDIT_CARD":   OperatorConfig("mask",    {"chars_to_mask": 12, "masking_char": "*", "from_end": False}),
    "US_SSN":        OperatorConfig("hash",    {"hash_type": "sha256", "salt": "my-salt"}),
    "PHONE_NUMBER":  OperatorConfig("encrypt", {"key": "WmZq4t7w!z%C&F)J"}),
    "DEFAULT":       OperatorConfig("replace", {}),  # fallback for unlisted entity types
}
```

If `new_value` is omitted from `replace`, the default is `<ENTITY_TYPE>` (e.g. `<EMAIL_ADDRESS>`).

**⚠️ Hash operator breaking change (v2.2.361+):** hash now uses a **random salt by default**. Same PII text produces different hashes each run. For referential integrity (consistent pseudonymization across multiple runs/records), pass an explicit `salt` parameter.

---

### Batch Processing

For CSV de-identification, use `BatchAnonymizerEngine` instead of looping the regular engine — it handles DataFrames natively:

```python
from presidio_anonymizer import BatchAnonymizerEngine

batch_engine = BatchAnonymizerEngine()
anonymized_df = batch_engine.anonymize_dict(
    analyzer_results,
    operators=operators,
)
```

The current `run_pii_anonymization` in `tasks.py` does this manually in chunks. `BatchAnonymizerEngine` is a cleaner alternative if refactoring.

---

### Custom Recognizers

Add a regex-based recognizer (e.g. internal employee IDs):

```python
from presidio_analyzer import PatternRecognizer, Pattern

emp_id_recognizer = PatternRecognizer(
    supported_entity="EMPLOYEE_ID",
    patterns=[Pattern("Employee ID", r"EMP-\d{6}", score=0.85)],
    context=["employee", "staff", "id"],
)
engine.analyzer.registry.add_recognizer(emp_id_recognizer)
```

The PoC has `azure_ai_language_wrapper.py` showing a `RemoteRecognizer` for calling Azure AI Language PII service.

---

### Decision Process (Detection Rationale)

When `return_decision_process=True`, each result's `.analysis_explanation` has:
- `.recognizer` — name of the recognizer that fired
- `.pattern_name` — regex pattern name (for PatternRecognizers)
- `.pattern` — the actual regex
- `.original_score` — raw score before context boosting
- `.score` — final score after context enhancement
- `.textual_explanation` — human-readable reason

This is the data source for the **Detection Rationale** project board feature. Implement by passing this through `pii_engine.analyze()` return value and surfacing in the PII Text page entity table.

---

## Testing Reference

> Pattern from the PoC test suite (`cpsc4205-group3/anonymous-studio`) applied to v2.

---

### Testing Taipy Callbacks Without Running the UI

```python
from taipy.gui.utils._mocked_gui import MockedGui
from taipy.gui import State

def test_on_card_save():
    with MockedGui() as gui:
        state = State(gui, vars={"card_title_f": "", "card_form_open": True})
        on_card_save(state)
        assert not state.card_form_open  # or notify was called with error
```

Alternatively, mock `store` and test the business logic directly without Taipy:

```python
from unittest.mock import patch, MagicMock

def test_on_card_save_empty_title():
    mock_state = MagicMock()
    mock_state.card_title_f = ""
    with patch("app.notify") as mock_notify:
        on_card_save(mock_state)
        mock_notify.assert_called_with(mock_state, "error", "Title is required.")
```

### Testing `store.py` (pure Python, no Taipy needed)

```python
from store import get_store, PipelineCard

def test_add_and_get_card():
    store = get_store()
    c = PipelineCard(title="Test", status="backlog")
    store.add_card(c)
    assert store.get_card(c.id).title == "Test"
```

### Testing `pii_engine.py`

```python
from pii_engine import get_engine

def test_email_detected():
    engine = get_engine()
    results = engine.analyze("Contact jane@example.com", entities=["EMAIL_ADDRESS"])
    assert any(r.entity_type == "EMAIL_ADDRESS" for r in results)
```

---

## GUI Actions Quick Reference

All importable from `taipy.gui`:

```python
from taipy.gui import (
    notify,               # toast notification
    navigate,             # programmatic page navigation
    download,             # trigger browser file download
    invoke_long_callback, # background thread with GUI callback on completion
    invoke_callback,      # call a function on the GUI thread from any thread
    get_state_id,         # get state ID for cross-thread callbacks
    hold_control,         # disable a control (by id) during processing
    resume_control,       # re-enable a held control
    close_notification,   # close a persistent notify(duration=0) by id
)
```

### `download()` — for CSV export

```python
from taipy.gui import download

def on_download(state):
    sc = _SCENARIOS.get(state.download_scenario_id)
    anon_df = sc.anon_output.read()
    csv_bytes = anon_df.to_csv(index=False).encode()
    download(state, content=csv_bytes, name="anonymized_output.csv")
```

### `hold_control()` / `resume_control()` — prevent double-clicks

```python
def on_submit_job(state):
    hold_control(state, "submit_btn")      # disable the submit button
    invoke_long_callback(state, _bg_submit_job, ..., user_status_function=_bg_done)

def _bg_done(state, status, result):
    resume_control(state, "submit_btn")    # re-enable after job queued
```

---

## Module-Level Caches (Thread Safety Note)

Two module-level dicts serve as cross-thread state (bypass Taipy's JSON serialization):

| Dict | Key | Value | Purpose |
|------|-----|-------|---------|
| `_FILE_CACHE` | `"bytes"` / `"name"` | raw bytes, filename | Uploaded file bytes (bytes → str in JSON) |
| `_SCENARIOS` | `job_id` (str) | `tc.Scenario` | Scenario reference for result loading |

Both are safe in single-process (`development`) mode. In `standalone` mode with multiple worker processes they would not be shared — use a database or shared filesystem instead.


---

## PoC Feature Parity Reference

> The original Presidio Streamlit demo (`cpsc4205-group3/anonymous-studio`, itself based on https://microsoft.github.io/presidio/samples/python/streamlit/) defined the feature set. This table maps each PoC feature to its v2 status.

| PoC Feature | v2 Status | Notes |
|-------------|-----------|-------|
| Text input + detect + anonymize | ✅ Done | PII Text page |
| Entity type selector | ✅ Done | Static `ALL_ENTITIES` list |
| Threshold slider | ✅ Done | Default 0.35 |
| Operators: replace, redact, mask, hash | ✅ Done | |
| Highlighted output | ✅ Done | `highlight_md()` — Taipy `mode=md` |
| Entity findings table | ✅ Done | entity_type, text, confidence, span |
| CSV/Excel batch upload + background job | ✅ Done (v2 new) | |
| Kanban pipeline | ✅ Done (v2 new) | |
| Audit log | ✅ Done (v2 new) | |
| **Operator: encrypt** | ⚠️ Partial | Listed in docs but `OperatorConfig("encrypt", {"key": key})` needs UI key field |
| **Operator: synthesize** | ❌ Missing | Needs `OPENAI_KEY`; prompt template in PoC's `openai_fake_data_generator.py` |
| **Allowlist** | ❌ Missing | Words that should NOT be flagged — pass as `allow_list=` to `analyzer.analyze()` |
| **Denylist** | ❌ Missing | Words that SHOULD be flagged — `ad_hoc_recognizers=[PatternRecognizer(entity="GENERIC_PII", deny_list=...)]` |
| **Detection rationale** | ❌ Missing (in progress) | `return_decision_process=True` → `.analysis_explanation` on each result |
| **ORGANIZATION entity** | ❌ Missing | Not in `ALL_ENTITIES`; requires NLP model (`ORG` → `ORGANIZATION` mapping) |
| Multiple NER models (HuggingFace, Stanza, Flair, Azure) | ❌ Out of scope | PoC has `presidio_nlp_engine_config.py` with full config for all; Azure wrapper in `azure_ai_language_wrapper.py` |

---

### Allowlist / Denylist Implementation Pattern

From `presidio_helpers.py` in the PoC:

```python
# Allowlist — words that should NOT be flagged as PII
results = analyzer.analyze(
    text=text,
    entities=entities,
    language="en",
    score_threshold=threshold,
    allow_list=["John", "Smith"],   # these names are safe context in this doc
)

# Denylist — words that MUST be flagged as GENERIC_PII
from presidio_analyzer import PatternRecognizer

deny_recognizer = PatternRecognizer(
    supported_entity="GENERIC_PII",
    deny_list=["Acme Corp", "Project X"],
)
results = analyzer.analyze(
    text=text,
    entities=entities + ["GENERIC_PII"],
    language="en",
    ad_hoc_recognizers=[deny_recognizer],
)
```

Add these as optional text-tag inputs on the PII Text page.

---

### Synthesize Operator Pattern

From `openai_fake_data_generator.py` in the PoC:

```python
# Step 1: anonymize with replace to get <ENTITY> placeholders
replaced = anonymizer.anonymize(text, analyze_results, operators={"DEFAULT": OperatorConfig("replace", {})})

# Step 2: prompt GPT to fill in realistic fake values
prompt = f"""
Replace placeholders like <PERSON>, <EMAIL_ADDRESS> with realistic fake values.
Keep formatting identical. Only output the replaced text.

Input: {replaced.text}
Output:"""

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
response = client.completions.create(model="gpt-3.5-turbo-instruct", prompt=prompt, max_tokens=256)
fake_text = response.choices[0].text.strip()
```

Env vars: `OPENAI_KEY` (OpenAI) or `AZURE_OPENAI_KEY` + `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_DEPLOYMENT` + `OPENAI_API_VERSION` (Azure OpenAI). Gate behind a feature flag — don't crash if key is absent.

---

### ORGANIZATION Entity — NLP Mapping Gap

The PoC's NlpEngine config maps spaCy's `ORG` tag → `ORGANIZATION`. This entity is NOT in v2's `ALL_ENTITIES`. To add it:

1. Add `"ORGANIZATION"` to `ALL_ENTITIES` in `pii_engine.py`
2. Verify the NlpEngineProvider config in `pii_engine.py` has the mapping:
   ```python
   "ner_model_configuration": {
       "model_to_presidio_entity_mapping": {
           "ORG": "ORGANIZATION",
           "ORGANIZATION": "ORGANIZATION",
           ...
       },
       "low_confidence_score_multiplier": 0.4,   # PoC uses this to reduce ORG false positives
       "low_score_entity_names": ["ORG", "ORGANIZATION"],
   }
   ```

The PoC intentionally applies a `0.4` confidence multiplier to ORG detections because organization names have high false-positive rates.

---

### Encrypt Operator — Key Management

The PoC uses a hardcoded demo key `"WmZq4t7w!z%C&F)J"`. For real use, the encrypt key must be:
- 128-bit (16 chars), 192-bit (24 chars), or 256-bit (32 chars) AES key
- Stored securely (env var, not hardcoded)
- The same key used for `DeanonymizeEngine` to reverse the encryption

```python
from presidio_anonymizer import DeanonymizeEngine
from presidio_anonymizer.entities import OperatorResult, OperatorConfig

deengine = DeanonymizeEngine()
original = deengine.deanonymize(
    text=anonymized_text,
    entities=[OperatorResult(start=..., end=..., entity_type="PERSON")],
    operators={"DEFAULT": OperatorConfig("decrypt", {"key": encryption_key})},
)
```

