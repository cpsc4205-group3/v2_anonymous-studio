# Anonymous Studio — Project Steering Prompt
# Paste this at the start of any new Claude conversation to get up to speed instantly.

---

You are helping build **Anonymous Studio**, a PII de-identification platform for a university software engineering course.

## Course Context
- **Course:** CPSC 4205 — Software Engineering
- **Group 3:** Carley Fant, Sakshi Patel, Diamond Hogans, Elijah Jenkins
- **Timeline:** 5 sprints over 10 weeks (Jan 26 – Mar 2, 2026)
- **Stage:** Core application built and working. Now refining, fixing bugs, and adding polish.

---

## What the App Does

Anonymous Studio lets users upload datasets (CSV, Excel) containing sensitive personal data, runs Microsoft Presidio to detect and anonymize PII, and manages the compliance workflow around that process.

**The five pages:**
1. **Dashboard** — live job counts, pipeline status, upcoming review appointments, recent audit activity
2. **PII Text** — paste any text, instantly highlights and anonymizes PII without uploading a file
3. **Upload & Jobs** — upload large CSV/Excel files, submit as background jobs, watch progress, download results
4. **Pipeline (Kanban)** — track de-identification tasks through Backlog → In Progress → Review → Done; linked to actual background job status
5. **Audit Log** — filterable, immutable log of every action taken in the system

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| UI | **Taipy GUI** | Markdown DSL, reactive state, `invoke_long_callback` for non-blocking UI |
| Pipeline | **taipy.core** | DataNodes, Tasks, Scenarios, Orchestrator for background job execution |
| PII Detection | **Microsoft Presidio** | Analyzer + Anonymizer |
| NLP | **spaCy** | Auto-detects best locally installed model; falls back to blank model if none found |
| Data | **pandas** | DataFrame I/O, chunked processing |
| Storage | **In-memory** (swap-ready for MongoDB) | `store.py` DataStore class |

---

## File Structure

```
anonymous_studio/
├── app.py           # Main Taipy GUI — all pages, state, and callbacks (~1200 lines)
├── core_config.py   # taipy.core: DataNodes, Task, Scenario, Orchestrator bootstrap
├── tasks.py         # run_pii_anonymization() — the actual pipeline function
├── pii_engine.py    # Presidio wrapper — analyze(), anonymize(), highlight_html()
├── store.py         # In-memory store: Kanban cards, appointments, audit log
├── config.toml      # Taipy VS Code extension config (mirrors core_config.py)
├── requirements.txt
├── README.md
└── docs/
    ├── spacy.md        # What spaCy is, model options, how auto-detection works
    ├── deployment.md   # Online vs offline, venv setup, production config
    └── architecture.md # taipy.core concepts, background job flow, known limitations
```

---

## How Background Jobs Work

This is the most important architectural piece — understand this before touching jobs or pipeline code.

```
User uploads CSV
       │
       ▼
on_submit_job() in app.py
       │
       ▼
invoke_long_callback()   ← UI stays responsive, never blocks
       │
       ▼  (background thread)
_bg_submit_job()
       │
       ▼
cc.submit_job(df, config)   ← core_config.py
       │
       ▼
tc.create_scenario(pii_scenario_cfg)
       │  writes raw_input DataNode (the DataFrame)
       │  writes job_config DataNode (operator, entities, threshold, chunk_size)
       ▼
tc.submit(scenario)
       │
       ▼  (Orchestrator picks up the job)
run_pii_anonymization(raw_df, job_config)   ← tasks.py
       │  auto-detects text columns
       │  processes in chunks (default 500 rows)
       │  writes PROGRESS_REGISTRY[job_id] every chunk
       ▼
writes anon_output DataNode (anonymized DataFrame)
writes job_stats DataNode (entity counts, timing, errors)
       │
       ▼
GUI polls PROGRESS_REGISTRY on "Refresh Progress" click
On completion: loads results, auto-advances linked Kanban card to Review
```

---

## taipy.core DataNodes

All are `SCENARIO`-scoped — every job gets fully isolated copies:

| DataNode | Type | Contents |
|----------|------|----------|
| `raw_input` | pickle | Uploaded DataFrame |
| `job_config` | pickle | `{job_id, operator, entities, threshold, chunk_size}` |
| `anon_output` | pickle | De-identified DataFrame |
| `job_stats` | pickle | `{total_entities, entity_counts, duration_s, errors, sample_before, sample_after}` |

---

## Execution Modes

```bash
# Development (default) — synchronous, works everywhere including restricted environments
ANON_MODE=development   # this is the default, no need to set it

# Production — true parallel worker subprocesses
ANON_MODE=standalone
ANON_WORKERS=4
```

---

## spaCy Model Resolution

`pii_engine.py` auto-detects the best available model at startup. No code changes needed — just install a model and restart.

```
Priority order:
1. $SPACY_MODEL env var     ← explicit override
2. en_core_web_lg           ← best accuracy (recommended)
3. en_core_web_md
4. en_core_web_sm
5. en_core_web_trf
6. Blank fallback           ← regex-only, PERSON/LOCATION/ORG not detected
```

Install: `python -m spacy download en_core_web_lg`

The active model is shown in a status banner on the PII Text and Upload & Jobs pages.

---

## Entity Types Detected (16 total)

`EMAIL_ADDRESS` · `PHONE_NUMBER` · `CREDIT_CARD` · `US_SSN` · `US_PASSPORT` · `US_DRIVER_LICENSE` · `US_ITIN` · `US_BANK_NUMBER` · `IP_ADDRESS` · `URL` · `IBAN_CODE` · `DATE_TIME` · `LOCATION` · `PERSON` · `NRP` · `MEDICAL_LICENSE`

---

## Anonymization Operators

| Operator | Output example |
|----------|---------------|
| `replace` | `<EMAIL_ADDRESS>` |
| `redact` | *(text deleted)* |
| `mask` | `********************` |
| `hash` | SHA-256 hex string |

---

## Design Spec

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
| Font | Syne (headings), IBM Plex Mono (code/output) |

---

## Known Limitations (be aware before suggesting changes)

1. **Kanban is tables, not cards** — Taipy has no native Kanban widget. Cards are rendered as table rows. No drag-and-drop. Users move cards with Forward/Back buttons. This is a known Taipy limitation, not a bug.

2. **PROGRESS_REGISTRY doesn't cross processes** — In `standalone` mode (separate worker processes), the progress dict in `tasks.py` won't be visible to the GUI process. Would need Redis or polling `job_stats` DataNode for real-time progress in production.

3. **In-memory store resets on restart** — `store.py` uses Python dicts. Pipeline cards, appointments, and audit log are lost when the app restarts. MongoDB integration is documented in `docs/deployment.md` and `store.py` is structured to make the swap straightforward.

4. **No authentication** — the app has no login. Fine for a course demo; needs Flask middleware or a reverse proxy before any real deployment.

---

## Development Setup

```bash
git clone <repo>
cd anonymous_studio
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # optional but recommended
python app.py
# → http://localhost:5000
```

---

## What NOT to Change Without Good Reason

- **`invoke_long_callback` pattern in `on_submit_job()`** — this is what keeps the UI non-blocking. Don't replace with a direct `tc.submit()` call in the callback.
- **`Scope.SCENARIO` on all DataNodes** — this is what isolates jobs from each other. Changing to `GLOBAL` would make concurrent jobs overwrite each other's data.
- **`_find_spacy_model()` resolution order in `pii_engine.py`** — the blank fallback at the end is intentional for restricted environments.
- **The `store.py` public interface** — `add_card`, `update_card`, `list_cards`, `log`, etc. are the contract that `app.py` depends on. Change internals freely, but keep the method signatures stable.