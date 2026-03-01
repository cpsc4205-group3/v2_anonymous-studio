## Anonymous Studio — Current State Summary

### Project Overview
A Taipy 4.x GUI application for PII detection and anonymization using Microsoft Presidio + spaCy. Six pages: Dashboard, PII Text, Upload & Jobs, Pipeline (Kanban), Schedule, Audit Log.

---

### Tech Stack
| Layer | Technology |
|---|---|
| UI Framework | Taipy GUI 4.x (Markdown controls, WebSocket state) |
| PII Engine | Microsoft Presidio (analyzer + anonymizer) |
| NLP Model | spaCy `en_core_web_lg` (blank fallback if not installed) |
| Orchestrator | Taipy Core (DataNodes, Scenarios, background jobs) |
| Data Store | In-memory Python ([store.py](cci:7://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:0:0-0:0)) |
| File Support | CSV, Excel (.xlsx/.xls) via pandas + openpyxl |

---

### Pages & Status

**Dashboard** — ✅ Working
- 6 stat cards (Jobs Submitted, Running, Completed, Failed, Pipeline Cards, Attested) with colored metric values
- Recent audit log table (last 4 entries)
- Upcoming reviews panel
- Full-width layout (MUI container override)

**PII Text** — ✅ Working
- Quick-scan text input with entity/operator selectors
- PII highlights rendered via [highlight_md()](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/pii_engine.py:296:0-317:25) using `mode=md` text control (replaced broken `raw=True` HTML approach)
- Entity table, summary count, anonymized output — all rendering

**Upload & Jobs** — ✅ Working
- CSV/Excel upload via `file_selector` — bytes cached in module-level `_FILE_CACHE` dict (bypasses Taipy JSON state serialization which converts bytes→str)
- Background job submission via `invoke_long_callback` → Taipy Orchestrator
- Job progress table, NLP model status banner

**Pipeline (Kanban)** — ✅ Working
- 4-column board: Backlog / In Progress / Review / Done
- Card forward/back with null-safe guard + `ValueError` catch on invalid `status`
- Attestation dialog (single audit entry — duplicate log removed)
- Correct Taipy scenario ID linked to card in [_bg_job_done](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:460:0-469:66) (was previously set to wrong UUID)

**Schedule** — ✅ Renders correctly
- Appointment table with add/edit/delete

**Audit Log** — ✅ Working
- Filterable by severity
- All actions logged (job.submit, pipeline.move, compliance.attest, app.start)

---

### Bugs Fixed This Session

| # | Bug | Root Cause | Fix |
|---|---|---|---|
| 1 | [store.stats()](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:219:4-242:9) TypeError | `dict_keys * 0` is invalid | Removed dead line, fixed loop indentation |
| 2 | `on_card_forward/back` crash | No null check on [store.get_card()](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:146:4-147:39) result; `ValueError` if bad status | Added `if not c: return` + `try/except ValueError` |
| 3 | Wrong `scenario_id` on linked card | `scenario_id` was set to the internal job UUID, not the Taipy scenario ID | [_bg_submit_job](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:449:0-457:34) now returns `(sc.id, job_id)`; [_bg_job_done](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:460:0-469:66) updates the card |
| 4 | Duplicate attestation audit entry | [on_attest_confirm](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:733:0-741:51) called [log_user_action](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:213:4-215:79) redundantly (store already logs) | Removed extra [log_user_action](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:213:4-215:79) call |
| 5 | PII highlights not rendering | `raw=True` not supported for HTML in Taipy 4.x `text` control | Implemented [highlight_md()](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/pii_engine.py:296:0-317:25) in [pii_engine.py](cci:7://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/pii_engine.py:0:0-0:0), switched to `mode=md` |
| 6 | CSV upload: both fail + success alerts | Taipy's `file_selector` fires `on_action` twice (once valid, once spurious cancel) | Silent `return` when `path` is missing/invalid |
| 7 | CSV parse: "bytes-like object required, not str" | Taipy serializes state as JSON — bytes stored in state become strings | Binary file content cached in module-level `_FILE_CACHE` dict; [on_submit_job](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:455:0-518:43) falls back to bound-var bytes or path-string if cache misses |

---

### Known Remaining Items (Low Priority)

- **`store.list_appts()` / `store.upcoming_appts()`** — wrong method names called in [app.py](cci:7://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:0:0-0:0); correct names are [list_appointments()](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:184:4-188:9) / [upcoming_appointments()](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:190:4-194:70). Currently masked because the refresh helpers catch exceptions silently.
- **`store` has no `get_appointment()` public method** — [on_appt_edit](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:783:0-799:31) accesses `_appointments` dict directly (internal access).
- **[update_appointment](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:169:4-176:19) / [delete_appointment](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/store.py:178:4-182:20)** leave no audit trail.
- **[_resolve_job_status](cci:1://file:///home/51nk0r5w1m/school/capstone/v2_anonymous-studio/app.py:195:0-216:24) uses `tc.get_parents()`** — key access pattern needs verification against the live Taipy 4.x API.
- **spaCy model not installed** — running in blank-fallback mode; PERSON/LOCATION/ORG entities not detected. Fixable with `python -m spacy download en_core_web_lg`.

---

### File Structure
```
app.py          — Main Taipy GUI (state, callbacks, page markup, CSS)
pii_engine.py   — Presidio wrapper + highlight_md()
tasks.py        — run_pii_anonymization (Taipy Core task function)
store.py        — In-memory data store (PIISession, PipelineCard, Appointment, AuditEntry)
core_config.py  — Programmatic Taipy Core configuration (DataNodes, Scenarios)
config.toml     — Declarative mirror of core_config.py (for VS Code extension)
requirements.txt — Python deps (taipy, presidio, spacy, pandas, openpyxl, etc.)
```