# Anonymous Studio — De-Identified Data Pipelines
**CPSC 4205 | Group 3 | Spring 2026**
*Carley Fant · Sakshi Patel · Diamond Hogans · Elijah Jenkins*

---

## Taipy Studio (Recommended)

Taipy Studio is a VS Code extension that makes building Taipy apps significantly faster. Install it before writing any new pages or modifying `core_config.py`.

### What it gives you

**Configuration Builder** — a point-and-click editor for taipy.core config files (`.toml`). Instead of manually writing DataNode, Task, and Scenario declarations, you build them visually and Taipy Studio generates the config. Opens in the VS Code Secondary Side Bar under "Taipy Configs".

**GUI Helper** — IntelliSense inside the Taipy Markdown DSL (`<|...|component|prop=value|>`). As you type visual element properties in `.md` files or Python strings, it autocompletes component names, property names, and variable references. Also includes a variable explorer and code navigation.

### Install

1. Make sure Taipy 3.0+ is installed in your venv (it is — `requirements.txt` pins `taipy>=3.1.0`)
2. Open VS Code → Extensions (`Ctrl+Shift+X`) → search **"Taipy"**
3. Install **Taipy Studio** — it automatically pulls in both sub-extensions

> Taipy Studio 2.0+ is required for Taipy 3.x. If you see a 1.x version in the marketplace, make sure you select 2.0 or later.

### Relevance to this project

| Taipy Studio feature | Where it helps in Anonymous Studio |
|---------------------|------------------------------------|
| Config Builder | Editing DataNodes / Tasks in `core_config.py` visually |
| GUI Helper IntelliSense | Writing page strings (`DASH`, `JOBS`, `PIPELINE`, etc.) in `app.py` |
| Variable explorer | Seeing all reactive state variables without reading the full file |
| `.toml` config view | If you migrate from inline `Config.configure_*` calls to a `.toml` file |

### Migrating to a `.toml` config (optional)

Right now `core_config.py` declares everything in Python. Taipy also supports `.toml` configuration files, which the Config Builder edits visually. If you want to use the GUI for your DataNode and Scenario setup:

```bash
# Export current config to toml (run once inside the venv)
python -c "from core_config import *; from taipy import Config; Config.export('config.toml')"
```

Then open `config.toml` in VS Code — Taipy Studio will show it in the Taipy Configs panel.

---



```
┌─────────────────────────────────────────────────────────┐
│  Taipy GUI  (app.py)                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │Dashboard │ │Upload/   │ │Pipeline  │ │Schedule/ │  │
│  │          │ │Jobs      │ │Kanban    │ │Audit     │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
└───────┼────────────┼────────────┼────────────┼─────────┘
        │            │ invoke_    │            │
        │            │ long_      │            │
        ▼            ▼ callback   ▼            ▼
┌───────────────────────────────────────────────────────┐
│  taipy.core  (core_config.py)                         │
│                                                       │
│  DataNode: raw_input  ──┐                             │
│  DataNode: job_config ──┤──► Task: anonymize_task     │
│                          │      │                     │
│  DataNode: anon_output ◄─┤      └── tasks.py          │
│  DataNode: job_stats   ◄─┘          run_pii_          │
│                                     anonymization()   │
│  Scenario: pii_pipeline                               │
│  Orchestrator (development | standalone)              │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  pii_engine.py           │
│  Presidio Analyzer       │
│  + AnonymizerEngine      │
│  (offline spaCy, no net) │
└──────────────────────────┘
```

## How Background Jobs Work

1. **User uploads** a CSV/Excel file on the Jobs page
2. **`invoke_long_callback`** fires — the GUI stays fully responsive
3. The callback thread calls **`cc.submit_job(df, config)`**
4. `submit_job` creates a fresh **taipy.core Scenario**, writes the two input DataNodes (`raw_input`, `job_config`), and calls `tc.submit(scenario)`
5. The Orchestrator picks up the job and runs **`run_pii_anonymization`** (in `tasks.py`):
   - Auto-detects text/PII columns
   - Processes in configurable chunks (default 500 rows)
   - Writes per-chunk progress to **`PROGRESS_REGISTRY`** dict
   - Returns `(anonymized_df, stats)` → written to output DataNodes
6. The GUI polls **`PROGRESS_REGISTRY`** when the user clicks "Refresh Progress"
7. On completion, results load into the preview table; the linked Kanban card auto-advances to **Review**

### Switching to True Parallel Workers (Production)
```bash
export ANON_MODE=standalone
export ANON_WORKERS=8
python app.py
```
No code changes needed — `core_config.py` reads the env var.

---

## Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Live job counts, pipeline status, upcoming reviews, recent audit |
| **PII Text** | Inline text analysis — highlights + anonymizes without file upload |
| **Upload & Jobs** | Submit large CSV/Excel as background jobs; progress bar; result preview + download |
| **Pipeline** | Kanban board (Backlog → In Progress → Review → Done) linked to job status |
| **Schedule** | Book and track PII review appointments, linked to pipeline cards |
| **Audit Log** | Filterable immutable log of every system and user action |

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/cpsc4205-group3/anonymous-studio.git
cd anonymous-studio
```

### 2. Check your Python version

```bash
python --version
```

**You need Python 3.10, 3.11, 3.12, or 3.13.** Python 3.14 is not supported — Presidio and spaCy do not publish wheels for it yet and the install will fail.

If you have 3.14, install 3.12 from [python.org](https://python.org) and use it explicitly in the next step.

### 3. Create and activate a virtual environment

```bash
# Use python3.12 explicitly to avoid picking up 3.14 if both are installed
python3.12 -m venv .venv

# Activate — run this every time you open a new terminal
source .venv/bin/activate        # Mac / Linux
.venv\Scripts\activate           # Windows
```

You'll see `(.venv)` at the start of your prompt when it's active. Run `python --version` inside the venv to confirm it shows 3.12.x.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Download the spaCy NER model (recommended)

Run this **while the venv is active** so the model installs into `.venv` and not system Python.

```bash
python -m spacy download en_core_web_lg
```

This enables detection of free-text entity types: `PERSON`, `LOCATION`, and `ORGANIZATION`. Without it the app still works but will only detect structured PII (emails, SSNs, phone numbers, credit cards, etc.). The app auto-detects whichever model is installed — no code change needed.

> **Can't download right now?** Skip this step. The app falls back to a blank model automatically and shows a warning banner in the UI.

### 6. Run

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

### 7. Add to `.gitignore`

```
.venv/
__pycache__/
*.pyc
user_data/
/tmp/anon_studio_blank_en/
```

`user_data/` is where taipy.core writes DataNode pickles (job inputs and outputs). `/tmp/anon_studio_blank_en/` is the blank spaCy model fallback. Neither should be committed.

---

### Optional: real MongoDB

The app ships with an in-memory store — data resets on every restart. To persist pipeline cards, appointments, and the audit log, replace the `DataStore` internals in `store.py` with a pymongo-backed implementation. The public interface (`add_card`, `update_card`, `list_cards`, `log`, etc.) is unchanged so nothing else needs to be modified.

```bash
pip install pymongo
```

```python
# store.py — set at the top
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
```

---

## File Structure

```
anonymous_studio/
├── app.py           Main Taipy GUI — all pages, state, callbacks
├── core_config.py   taipy.core: DataNodes, Task, Scenario, Orchestrator
├── tasks.py         run_pii_anonymization() — the actual pipeline function
├── pii_engine.py    Presidio wrapper — analyze(), anonymize(), highlight_html()
├── store.py         In-memory store for Kanban cards, appointments, audit log
└── requirements.txt
```

## Entity Types Detected
`EMAIL_ADDRESS` · `PHONE_NUMBER` · `CREDIT_CARD` · `US_SSN` · `US_PASSPORT`
`US_DRIVER_LICENSE` · `US_ITIN` · `US_BANK_NUMBER` · `IP_ADDRESS` · `URL`
`IBAN_CODE` · `DATE_TIME` · `LOCATION` · `PERSON` · `NRP` · `MEDICAL_LICENSE`

## Anonymization Operators
| Operator | Example output |
|----------|---------------|
| `replace` | `<EMAIL_ADDRESS>` |
| `redact`  | *(text deleted)* |
| `mask`    | `********************` |
| `hash`    | `a665a45920...` (SHA-256) |