# Deployment Notes — Online vs Offline Environments

## Overview

Anonymous Studio is designed to run in both **fully connected** and **air-gapped / restricted** environments. This document explains what changes between the two, what stays the same, and what you should set up before going to production.

---

## What requires internet access at startup

| Dependency | What it fetches | Required? |
|------------|-----------------|-----------|
| spaCy model | Model weights from `github.com/explosion/spacy-models` | Only if using a trained model |
| `tldextract` | Public Suffix List from `publicsuffix.org` | No — falls back gracefully |
| Google Fonts (GUI) | `fonts.googleapis.com` | No — UI still works, font changes |

Everything else — Presidio, Taipy, pandas, the entire processing pipeline — runs locally with no outbound calls.

---

## Environment configurations

### Development / Local (default)

```bash
# .env or shell
ANON_MODE=development      # synchronous task execution
```

No additional setup. Runs as-is with the blank spaCy model.

---

### Online production (recommended)

```bash
# Install full spaCy model once — app auto-detects it on next startup
python -m spacy download en_core_web_lg

# Set env vars
ANON_MODE=standalone       # true background worker processes
ANON_WORKERS=4             # number of parallel job workers
```

No code changes needed. The app checks for installed models at startup in preference order (`lg` → `md` → `sm` → `trf` → blank fallback) and logs which one was loaded. The active model is shown in the UI status banner.

---

### Air-gapped / offline production

You can pre-package the spaCy model into your deployment artifact:

```bash
# On a machine WITH internet access:
python -m spacy download en_core_web_lg
python -m spacy package en_core_web_lg ./dist --build wheel
# Copy dist/en_core_web_lg-*.whl into your repo

# On the air-gapped machine:
pip install ./dist/en_core_web_lg-3.7.1-py3-none-any.whl --no-index
```

Then update `pii_engine.py` to point to the installed model name:
```python
_BLANK_PATH = "en_core_web_lg"
```

Alternatively, save the model to a known local path and load it directly:
```python
_BLANK_PATH = "/opt/models/en_core_web_lg"
# (run once: nlp = spacy.load("en_core_web_lg"); nlp.to_disk("/opt/models/en_core_web_lg"))
```

---

## Job execution modes

### `development` mode (default)

- Tasks run **synchronously** in the same process
- The GUI stays non-blocking because jobs are submitted via `invoke_long_callback` (a thread)
- Safe for: local development, single-user deployments, restricted sandbox environments
- Not suitable for: concurrent multi-user loads

### `standalone` mode (production)

- The Orchestrator spawns **real worker subprocesses**
- True parallelism — 10 jobs can run simultaneously
- Requires: a proper OS environment where `multiprocessing` subprocess spawning is permitted
- Set via: `ANON_MODE=standalone` + `ANON_WORKERS=N`

```
Development mode (one machine):
  GUI thread → invoke_long_callback → thread → taipy.core → task fn

Standalone mode (one machine, N workers):
  GUI thread → invoke_long_callback → thread → taipy.core → [Worker 1]
                                                            → [Worker 2]
                                                            → [Worker 3]
                                                            → [Worker N]
```

---

## MongoDB integration

The current `store.py` uses an in-memory Python dict — data is lost on restart. To connect to real MongoDB:

```python
# store.py — swap DataStore internals
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["anonymous_studio"]
```

The public interface (`add_card`, `update_card`, `list_cards`, `log`, etc.) stays identical — nothing in `app.py` or `core_config.py` needs to change.

---

## Cloud deployment

Anonymous Studio is stateless at the GUI layer. The Orchestrator and DataNodes are the stateful components.

### Azure App Service

```bash
# Recommended settings
ANON_MODE=standalone
ANON_WORKERS=4
ANON_STORAGE=/home/data/anon_jobs    # persistent disk mount
MONGO_URI=mongodb+srv://...          # Azure Cosmos DB or Atlas
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python -m spacy download en_core_web_lg   # bake model into image
COPY . .
ENV ANON_MODE=standalone
ENV ANON_WORKERS=4
EXPOSE 5000
CMD ["python", "app.py"]
```

---

## Security checklist before production

- [ ] **Authentication** — Taipy supports Flask middleware; add OAuth2 or JWT auth in front of the Gui
- [ ] **HTTPS** — run behind nginx or a cloud load balancer with TLS termination
- [ ] **File upload limits** — set `max_content_length` on the Flask app inside Taipy
- [ ] **Storage encryption** — encrypt DataNode pickle files at rest (or switch to encrypted MongoDB)
- [ ] **Audit log persistence** — connect `store.py` to MongoDB so the audit trail survives restarts
- [ ] **spaCy model version pinning** — pin `en_core_web_lg==3.7.1` in `requirements.txt` to avoid silent accuracy changes
- [ ] **Network egress rules** — Presidio's `tldextract` makes one outbound call at startup; safe to block in production (it falls back gracefully)

---

## Performance expectations

| Dataset size | Blank spaCy model | `en_core_web_lg` |
|-------------|-------------------|------------------|
| 1k rows | < 1s | ~3s |
| 10k rows | ~5s | ~25s |
| 100k rows | ~45s | ~4 min |
| 1M rows | ~8 min | ~40 min |

*Measured on a single core. Standalone mode with 4 workers gives roughly 3–3.5× speedup for large jobs by processing multiple chunks in parallel.*

Chunk size (`job_chunk_size`, default 500) trades latency for memory. For very large files on memory-constrained machines, reduce to 100–200. For fast machines with ample RAM, increase to 2000–5000 for better throughput.
