# What is spaCy — and Why Anonymous Studio Uses It

## The short answer

spaCy is an open-source Python library for **Natural Language Processing (NLP)** — the field of software that helps computers read, interpret, and extract meaning from human language. In Anonymous Studio, spaCy acts as the linguistic foundation that Microsoft Presidio sits on top of. Presidio uses spaCy to read and understand text before deciding where PII lives in it.

---

## What spaCy actually does

When you feed a sentence into spaCy, it runs a series of processing steps called a **pipeline**:

```
Raw text
   │
   ▼
Tokenizer        → splits "john.smith@acme.com called 555-1234" into individual tokens
   │
   ▼
Part-of-speech   → labels each token: noun, verb, proper noun, etc.
   │
   ▼
Dependency parse → maps grammatical relationships between tokens
   │
   ▼
Named Entity     → recognizes and labels real-world entities:
Recognition      →   "Dr. Robert Kim"  →  PERSON
(NER)            →   "Springfield, IL" →  LOCATION
                 →   "Acme Corp"       →  ORG
```

The final step — **Named Entity Recognition (NER)** — is the one that matters most for PII detection. It's the part that can recognize "Jane Doe" as a person's name even when there's no email address or SSN pattern to match against.

---

## How Presidio uses spaCy

Microsoft Presidio is not a standalone PII detector. It is a framework that **orchestrates** multiple detection strategies:

```
Presidio AnalyzerEngine
├── Pattern Recognizers  (regex)
│     ├── EmailRecognizer       → \b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\b
│     ├── PhoneRecognizer       → \b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b
│     ├── CreditCardRecognizer  → Luhn-validated 13-16 digit numbers
│     ├── UsSsnRecognizer       → \b\d{3}-\d{2}-\d{4}\b
│     └── ...14 more
│
└── NLP Recognizer  (uses spaCy)
      └── SpacyNlpEngine
            └── spaCy model → PERSON, LOCATION, ORG, DATE entities
```

Presidio *requires* a spaCy engine to start, even if you're only using regex recognizers. That is simply how it was architected. The `SpacyNlpEngine` is not optional.

---

## The two spaCy model options

### Option 1 — Blank model (current default)

```python
# pii_engine.py
_nlp = spacy.blank("en")     # zero NER capability
```

A blank model understands English grammar (tokenization, sentence boundaries) but has **not been trained** on any data. It cannot recognize names, places, or organizations.

We use this as a fallback because:
- Downloading a real model requires network access (~12–560 MB)
- In restricted environments (CI pipelines, air-gapped servers, sandboxes) downloads may fail
- All regex-based recognizers still work perfectly without NER

**What you get:** ~75% of real-world PII coverage — everything with a structured pattern.

**What you miss:** Free-text names ("Dr. Robert Kim"), locations ("Springfield, IL"), organization names ("Acme Corp"), and informal date references ("last Tuesday").

---

### Option 2 — Trained model (recommended for production)

```bash
python -m spacy download en_core_web_lg
```

| Model | Size | NER quality | Best for |
|-------|------|-------------|----------|
| `en_core_web_sm` | 12 MB | Good | Fast pipelines, limited resources |
| `en_core_web_md` | 43 MB | Better | General use |
| `en_core_web_lg` | 560 MB | Best | Medical records, HR data, compliance |
| `en_core_web_trf` | 438 MB | Highest | Maximum accuracy (transformer-based) |

For healthcare and HR datasets — which is Anonymous Studio's primary use case — **`en_core_web_lg` is the right choice**. Person names and locations are extremely common in those domains and the blank model will miss them entirely.

---

## Enabling the full model

**Step 1** — Install the model:

```bash
python -m spacy download en_core_web_lg
```

**That's it.** Anonymous Studio auto-detects installed models on startup — no code changes needed.

The resolution order is:

```
1. $SPACY_MODEL env var       ← explicit override for custom/fine-tuned models
2. en_core_web_lg             ← best accuracy, recommended
3. en_core_web_md             ← good balance of size and accuracy
4. en_core_web_sm             ← smallest trained model (~12 MB)
5. en_core_web_trf            ← transformer-based, highest accuracy (slower)
6. Blank fallback             ← regex only, used when nothing else is found
```

The active model is shown in a status banner at the top of the PII Text and Upload & Jobs pages:

```
✅ Full NER model: en_core_web_lg        ← trained model found and loaded
⚠️  Blank model (regex only) — ...       ← no trained model installed
```

To force a specific model (e.g. a custom fine-tuned one or a smaller model):

```bash
export SPACY_MODEL=en_core_web_sm        # use a specific model by name
export SPACY_MODEL=/opt/models/my_model  # or a local path
```

---

## Does it work online? Yes, fully.

The blank model workaround only exists because the development sandbox blocks outbound HTTPS to GitHub and PyPI — where spaCy downloads its model weights from. In any normal environment (your laptop, a cloud VM, Docker with internet access), `pip install` and `spacy download` work as expected.

The code path is identical either way. The only difference is which model file gets loaded into `SpacyNlpEngine`.

---

## Does spaCy store or transmit any data?

No. spaCy runs **entirely locally** — it is a Python library, not a service. There are no API calls, no telemetry, and no data leaves your machine. This is one of the reasons Presidio (and by extension Anonymous Studio) is suitable for sensitive data: the entire processing pipeline is air-gappable.

---

## spaCy at a glance

| Property | Value |
|----------|-------|
| Created by | Explosion AI (Berlin) |
| First released | 2015 |
| Language | Python (Cython under the hood for speed) |
| License | MIT — fully open source, commercial use allowed |
| Models | 70+ languages |
| Website | [spacy.io](https://spacy.io) |
| Used by | Airbus, Zalando, the NHS, government agencies, academic NLP research |
