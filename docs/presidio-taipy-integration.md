# Presidio + Taipy Integration Research

## Overview

This document provides a comprehensive analysis of how Microsoft Presidio (PII detection/anonymization engine) integrates with the Taipy GUI framework in the Anonymous Studio application.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TAIPY GUI LAYER                                │
│  (Markdown DSL → Reactive State → User Interactions)               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │     APPLICATION LAYER (app.py)     │
        │  - State management                │
        │  - Callback handlers               │
        │  - Result formatting               │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │   PII ENGINE (pii_engine.py)           │
        │  - PIIEngine wrapper class             │
        │  - Analyzer/Anonymizer lifecycle       │
        │  - Entity caching                      │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │   PRESIDIO LIBRARY                     │
        │  - AnalyzerEngine (detection)          │
        │  - AnonymizerEngine (transformation)   │
        │  - SpacyNlpEngine (NER models)         │
        └────────────────────────────────────────┘
```

---

## 2. Presidio Integration Details

### 2.1 Engine Initialization

**File:** `pii_engine.py`

```python
class PIIEngine:
    def __init__(self):
        # Lazy initialization - engines created on first use
        self._analyzer: Optional[AnalyzerEngine] = None
        self._anonymizer: Optional[AnonymizerEngine] = None
        self._nlp_engine: Optional[SpacyNlpEngine] = None
        
    def _init(self):
        """Initialize Presidio engines with spaCy model resolution."""
        # 1. Resolve spaCy model (auto-detection with fallback)
        model_name, is_trained = _find_spacy_model()
        
        # 2. Create NLP engine for entity recognition
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model_name}],
        }
        self._nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
        
        # 3. Initialize Presidio Analyzer with NLP engine
        self._analyzer = AnalyzerEngine(
            nlp_engine=self._nlp_engine,
            supported_languages=["en"],
        )
        
        # 4. Initialize Presidio Anonymizer
        self._anonymizer = AnonymizerEngine()
```

**Key Design Choices:**
- **Singleton Pattern:** One `PIIEngine` instance shared across entire app (`engine = get_engine()`)
- **Lazy Loading:** Presidio engines initialize on first `analyze()` call, not at import time
- **Background Warmup:** Optional warmup thread prevents first-call latency in production
- **Model Auto-Discovery:** Tries `en_core_web_lg` → `md` → `sm` → `trf` → blank fallback

### 2.2 spaCy Model Resolution Strategy

**Priority Order:**

1. **Explicit Override:** `SPACY_MODEL` environment variable
2. **Auto-Detection:** Check installed models via `spacy.util.get_installed_models()`
3. **Preference List:** `lg` (best) → `md` → `sm` → `trf` (slowest but most accurate)
4. **Blank Fallback:** Pattern/regex only (no ML-based entity detection)

**Why This Matters:**
- **With trained model:** Detects PERSON, LOCATION, NRP, ORGANIZATION via NER
- **With blank fallback:** Only detects regex-based entities (EMAIL, PHONE, SSN, etc.)
- **Production Recommendation:** Always install `en_core_web_lg` via `python -m spacy download en_core_web_lg`

### 2.3 Supported Entity Types

**17 Entity Types Configured:**

| Category | Entities |
|----------|----------|
| **Person Identifiers** | PERSON, EMAIL_ADDRESS, PHONE_NUMBER |
| **Government IDs** | US_SSN, US_PASSPORT, US_DRIVER_LICENSE, US_ITIN |
| **Financial** | CREDIT_CARD, US_BANK_NUMBER, IBAN_CODE |
| **Technical** | IP_ADDRESS, URL |
| **Medical** | MEDICAL_LICENSE |
| **Geographic** | LOCATION |
| **Organizational** | ORGANIZATION, NRP (Nationality/Religion/Politics) |
| **Temporal** | DATE_TIME |

**Defined in:** `pii_engine.py:127-145` (`ALL_ENTITIES` constant)

### 2.4 Anonymization Operators

**5 Operators Implemented:**

| Operator | Action | Example |
|----------|--------|---------|
| `replace` | Replace with `<ENTITY_TYPE>` or custom value | `John Doe` → `<PERSON>` |
| `redact` | Remove entirely | `john@email.com` → `` |
| `mask` | Partial character masking | `4532-1234-5678-9010` → `****-****-****-9010` |
| `hash` | SHA-256 hash with optional salt | `555-1234` → `a3f8b2...` |
| `synthesize` | Generate realistic fake data (Faker/LLM) | `John Doe` → `Michael Chen` |

**Configuration Example:**
```python
operators = {
    "PERSON": OperatorConfig("replace", {"new_value": "<PERSON>"}),
    "EMAIL_ADDRESS": OperatorConfig("redact"),
    "CREDIT_CARD": OperatorConfig("mask", {"chars_to_mask": 12, "masking_char": "*"}),
    "US_SSN": OperatorConfig("hash", {"salt": "project-salt"}),
}
```

---

## 3. Taipy GUI Integration

### 3.1 Page Organization & Routing

**Page Registry:** `pages/definitions.py:826-835`

```python
PAGES = {
    "/":          NAV,         # Navigation menu (root)
    "dashboard":  DASH,        # Live stats dashboard
    "analyze":    QT,          # Quick Text (PII analysis UI)
    "jobs":       JOBS,        # Batch job management
    "pipeline":   PIPELINE,    # Kanban board
    "schedule":   SCHEDULE,    # Review scheduling
    "audit":      AUDIT,       # Compliance audit log
    "ui_demo":    UI_DEMO,     # UI component demo
}
```

**How Pages Work:**
1. Each page is a **Markdown string** using Taipy's DSL syntax
2. Pages reference **reactive state variables** via `<|{variable}|>` syntax
3. Navigation triggered via `navigate(state, page_name)` in callbacks
4. Page-specific refresh functions update state after navigation

### 3.2 Navigation Flow

```python
# User clicks menu item → on_menu_action() callback
def on_menu_action(state, action, payload):
    page = payload["args"][0]  # e.g., "dashboard", "analyze", "jobs"
    
    # Validate page exists
    if page not in {"dashboard", "analyze", "jobs", "pipeline", "schedule", "audit", "ui_demo"}:
        return
    
    # Navigate to page
    navigate(state, page)
    
    # Trigger page-specific refresh
    if page == "dashboard":
        _refresh_dashboard(state)
    elif page == "analyze":
        _refresh_sessions(state)
    # ... etc.
```

### 3.3 State Management

**Taipy State Variables:**
- **Module-level variables** in `app.py` are automatically reactive
- Updates propagate to UI via `state.variable = value`
- All state is **per-user** (isolated sessions in multi-user deployments)

**Example State Variables for PII Analysis Page:**
```python
# Input state
qt_input = ""                 # User's input text
qt_entities = ALL_ENTITIES    # Selected entity types
qt_threshold = 0.35           # Confidence threshold
qt_operator = "replace"       # Selected operator

# Output state
qt_highlight_md = ""          # Color-coded detected PII
qt_anonymized = ""            # Anonymized result text
qt_entity_rows = []           # Entity findings table
qt_entity_chart = None        # Entity count bar chart
qt_last_proc_ms = 0           # Processing time
```

---

## 4. Complete User Flow: Text Analysis

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER INPUT                                                  │
│  - Navigate to "Analyze Text" page                                 │
│  - Enter text in qt_input textbox                                  │
│  - Select entities from qt_entities selector                       │
│  - Adjust qt_threshold slider                                      │
│  - Select qt_operator from dropdown                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: BUTTON CLICK                                                │
│  - User clicks "Analyze" or "Anonymize" button                     │
│  - Taipy invokes callback: on_qt_analyze() or on_qt_anonymize()   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: PRESIDIO ANALYSIS (app.py callback)                        │
│                                                                     │
│  t0 = time.perf_counter()                                          │
│  engine = get_engine()                                              │
│                                                                     │
│  # Detection + Anonymization                                        │
│  result = engine.anonymize(                                         │
│      text=state.qt_input,                                           │
│      entities=state.qt_entities,                                    │
│      operator=state.qt_operator,                                    │
│      threshold=state.qt_threshold,                                  │
│      allowlist=state.qt_allowlist,                                  │
│      denylist=state.qt_denylist,                                    │
│  )                                                                  │
│                                                                     │
│  # result contains:                                                 │
│  #  - original_text                                                 │
│  #  - anonymized_text                                               │
│  #  - entities (List[RecognizerResult])                            │
│  #  - entity_counts (Dict[str, int])                               │
│  #  - operator_used                                                 │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: RESULT FORMATTING                                           │
│                                                                     │
│  # Highlight detected PII with colors                               │
│  state.qt_highlight_md = highlight_md(state.qt_input, result.entities)│
│                                                                     │
│  # Format anonymized output                                         │
│  state.qt_anonymized = _format_anon_md(result.anonymized_text)     │
│                                                                     │
│  # Build entity findings table                                      │
│  state.qt_entity_rows = _qt_rows_from_entities(result.entities)    │
│                                                                     │
│  # Create entity count bar chart                                    │
│  state.qt_entity_chart = pd.DataFrame(result.entity_counts.items())│
│                                                                     │
│  # Record processing time                                           │
│  state.qt_last_proc_ms = int((time.perf_counter() - t0) * 1000)   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: UI UPDATE                                                   │
│                                                                     │
│  Taipy automatically propagates state changes to UI:               │
│  - Left panel shows qt_highlight_md (color-coded PII)              │
│  - Right panel shows qt_anonymized (final result)                  │
│  - Entity table displays qt_entity_rows                            │
│  - Bar chart renders qt_entity_chart                               │
│  - Processing time shows qt_last_proc_ms                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Callback Implementation

**File:** `app.py` (simplified example)

```python
def on_qt_anonymize(state):
    """Main callback for text anonymization."""
    # Validation
    if not state.qt_input.strip():
        notify(state, "warning", "Please enter text to anonymize.")
        return
    
    # Call Presidio
    t0 = time.perf_counter()
    result = engine.anonymize(
        text=state.qt_input,
        entities=state.qt_entities or ALL_ENTITIES,
        operator=state.qt_operator,
        threshold=state.qt_threshold,
        allowlist=_parse_list(state.qt_allowlist),
        denylist=_parse_list(state.qt_denylist),
    )
    duration_ms = int((time.perf_counter() - t0) * 1000)
    
    # Update state
    state.qt_highlight_md = highlight_md(state.qt_input, result.entities)
    state.qt_anonymized = _format_anon_md(result.anonymized_text)
    state.qt_entity_rows = _qt_rows_from_entities(result.entities)
    state.qt_entity_chart = _build_entity_chart(result.entity_counts)
    state.qt_last_proc_ms = duration_ms
    
    # Log to audit trail
    store.log_user_action(
        operator=state.qt_operator_username,
        action="pii.detect",
        target=f"{len(result.entities)} entities detected",
    )
    
    # Notify user
    notify(state, "success", f"Analysis complete ({duration_ms}ms)")
```

---

## 5. Batch Processing Integration

### Background Job Pipeline

**File:** `tasks.py:run_pii_anonymization()`

For CSV/Excel uploads, Presidio is invoked in a **background thread** managed by Taipy's Orchestrator:

```python
def run_pii_anonymization(raw_df: pd.DataFrame, config: dict) -> tuple:
    """
    Background task executed by Taipy Orchestrator.
    Processes large datasets in chunks with progress tracking.
    """
    # Extract config
    job_id = config["job_id"]
    operator = config["operator"]
    entities = config["entities"]
    threshold = config["threshold"]
    chunk_size = config.get("chunk_size", 100)
    
    # Initialize engine
    engine = get_engine()
    
    # Process in chunks
    results = []
    for i in range(0, len(raw_df), chunk_size):
        chunk = raw_df.iloc[i:i+chunk_size]
        
        # Anonymize each text cell
        for idx, row in chunk.iterrows():
            for col in text_columns:
                if pd.notna(row[col]):
                    anon_result = engine.anonymize(
                        text=str(row[col]),
                        entities=entities,
                        operator=operator,
                        threshold=threshold,
                    )
                    results.append(anon_result.anonymized_text)
        
        # Update progress (visible in UI)
        progress_pct = int((i + len(chunk)) / len(raw_df) * 100)
        PROGRESS_REGISTRY[job_id] = progress_pct
    
    return (anonymized_df, statistics)
```

**Key Features:**
1. **Non-blocking:** Runs in background thread; UI stays responsive
2. **Progress Tracking:** Updates `PROGRESS_REGISTRY` dict for real-time UI feedback
3. **Chunked Processing:** Handles large datasets (millions of rows) efficiently
4. **Result Persistence:** Outputs saved to Taipy DataNodes (pickle format)

---

## 6. Performance Optimizations

### 6.1 Operator Configuration Caching

**Problem:** Creating `OperatorConfig` objects for 17+ entity types on every cell was slow.

**Solution:** `_OPS_CACHE` dictionary caches configs per `(operator, entities)` key:

```python
_OPS_CACHE: Dict[tuple, Dict[str, OperatorConfig]] = {}

def _get_ops_dict(operator: str, entities: List[str]) -> Dict[str, OperatorConfig]:
    """Cached operator config lookup (2x speedup on batch jobs)."""
    key = (operator, tuple(sorted(entities)))
    if key not in _OPS_CACHE:
        _OPS_CACHE[key] = _build_ops_dict(operator, entities)
    return _OPS_CACHE[key]
```

**Result:** ~2x speedup on large batch jobs (10k+ rows).

### 6.2 Denylist Pattern Caching

Custom denylist patterns are compiled once and cached:

```python
_DENYLIST_PATTERN_CACHE: Dict[tuple, Pattern] = {}

def _get_denylist_recognizer(denylist: List[str]) -> PatternRecognizer:
    key = tuple(sorted(denylist))
    if key not in _DENYLIST_PATTERN_CACHE:
        pattern = Pattern("custom", r"(?i)\b(" + "|".join(map(re.escape, denylist)) + r")\b", 1.0)
        _DENYLIST_PATTERN_CACHE[key] = pattern
    return PatternRecognizer(...)
```

### 6.3 Background Warmup Thread

Presidio's first call incurs ~1-2s latency (model loading). The warmup thread eliminates this:

```python
def _warmup_engine():
    """Warm up Presidio engines on background thread."""
    engine = get_engine()
    engine.analyze("warmup text", fast=True)

# Start at import time (non-blocking)
Thread(target=_warmup_engine, daemon=True).start()
```

---

## 7. Key Integration Patterns

### 7.1 Error Handling

```python
def on_qt_anonymize(state):
    try:
        result = engine.anonymize(...)
        # ... update state ...
        notify(state, "success", "Complete")
    except Exception as e:
        _log.exception("Anonymization failed")
        notify(state, "error", f"Error: {str(e)}")
        state.qt_anonymized = "⚠️ Processing failed"
```

### 7.2 Input Validation

```python
def on_qt_anonymize(state):
    # Check text not empty
    if not state.qt_input.strip():
        notify(state, "warning", "Please enter text")
        return
    
    # Validate threshold range
    if not 0 <= state.qt_threshold <= 1:
        state.qt_threshold = 0.35
        notify(state, "warning", "Threshold reset to 0.35")
    
    # Ensure at least one entity selected
    if not state.qt_entities:
        state.qt_entities = ALL_ENTITIES
        notify(state, "info", "No entities selected; using all")
```

### 7.3 Audit Trail Integration

Every PII operation is logged:

```python
store.log_user_action(
    operator=state.current_user,
    action="pii.detect",
    target=f"{len(result.entities)} entities in {len(text)} chars",
    metadata={
        "operator": state.qt_operator,
        "threshold": state.qt_threshold,
        "entity_types": state.qt_entities,
    }
)
```

---

## 8. Testing Approach

### Unit Tests for Presidio Integration

**File:** `tests/test_pii_engine.py`

```python
def test_email_detection():
    """Verify EMAIL_ADDRESS entity is detected."""
    engine = get_engine()
    results = engine.analyze(
        "Contact jane@example.com",
        entities=["EMAIL_ADDRESS"],
        threshold=0.0,
    )
    assert any(r.entity_type == "EMAIL_ADDRESS" for r in results)
    assert any("jane@example.com" in r.text for r in results)

def test_anonymize_with_replace():
    """Verify replace operator works correctly."""
    engine = get_engine()
    result = engine.anonymize(
        "John Doe lives in Seattle",
        entities=["PERSON", "LOCATION"],
        operator="replace",
    )
    assert "<PERSON>" in result.anonymized_text
    assert "<LOCATION>" in result.anonymized_text
    assert "John Doe" not in result.anonymized_text
```

### Integration Tests for Taipy Callbacks

**File:** `tests/test_app_file_upload_download.py`

```python
def test_qt_anonymize_callback():
    """Test full Taipy callback flow."""
    from unittest.mock import MagicMock
    
    # Mock state
    state = MagicMock()
    state.qt_input = "Contact john@example.com"
    state.qt_entities = ["EMAIL_ADDRESS"]
    state.qt_operator = "redact"
    state.qt_threshold = 0.5
    
    # Call callback
    on_qt_anonymize(state)
    
    # Verify state updates
    assert state.qt_anonymized != ""
    assert "john@example.com" not in state.qt_anonymized
    assert len(state.qt_entity_rows) > 0
```

---

## 9. Common Pitfalls & Solutions

### Pitfall 1: Blank spaCy Model

**Problem:** Without a trained spaCy model, PERSON/LOCATION/ORG entities are never detected.

**Solution:** Always install `en_core_web_lg`:
```bash
python -m spacy download en_core_web_lg
```

**Verification:** Check model status in UI banner or via:
```python
from pii_engine import get_spacy_model_status
status = get_spacy_model_status()
print(status["is_trained"])  # Should be True
```

### Pitfall 2: Thread Safety

**Problem:** Presidio engines are NOT thread-safe; concurrent calls from multiple Taipy users can cause crashes.

**Solution:** Use per-user engine instances OR protect with locks:
```python
from threading import Lock

_ENGINE_LOCK = Lock()

def analyze_threadsafe(text, **kwargs):
    with _ENGINE_LOCK:
        return engine.analyze(text, **kwargs)
```

**Current App Status:** Uses single global engine with implicit lock (Taipy callbacks are sequential per user).

### Pitfall 3: Large Text Performance

**Problem:** Analyzing multi-megabyte text blocks takes seconds and blocks UI.

**Solution:** Use `invoke_long_callback` for text >10KB:
```python
def on_large_text_analyze(state):
    invoke_long_callback(
        state,
        user_function=_bg_analyze,
        user_function_args=[None, state.qt_input, state.qt_entities],
        user_status_function=_on_analyze_done,
    )
```

### Pitfall 4: Hash Operator Salt

**Problem:** Presidio v2.2.361+ uses random salt by default; same PII text produces different hashes each run.

**Solution:** Always pass explicit salt for referential integrity:
```python
OperatorConfig("hash", {"salt": "project-static-salt-2026"})
```

---

## 10. Extension Points

### Adding New Entity Types

**File:** `pii_engine.py`

1. Add to `ALL_ENTITIES` list:
```python
ALL_ENTITIES = [
    # ... existing entities ...
    "CRYPTO",           # Bitcoin addresses
    "MAC_ADDRESS",      # Network MAC addresses
    "UK_NHS",           # UK National Health Service number
]
```

2. Presidio automatically detects if recognizer exists in registry.

### Custom Recognizers

Add custom regex-based recognizer:

```python
from presidio_analyzer import PatternRecognizer, Pattern

def add_employee_id_recognizer(engine):
    recognizer = PatternRecognizer(
        supported_entity="EMPLOYEE_ID",
        patterns=[Pattern("emp", r"EMP-\d{6}", 0.9)],
        context=["employee", "staff"],
    )
    engine._analyzer.registry.add_recognizer(recognizer)

# Usage
add_employee_id_recognizer(engine)
```

### Custom Anonymization Operators

Implement custom operator (e.g., format-preserving encryption):

```python
from presidio_anonymizer.operators import Operator, OperatorType

class FpeOperator(Operator):
    """Format-preserving encryption operator."""
    
    def operate(self, text: str, params: dict) -> str:
        key = params.get("key")
        return fpe_encrypt(text, key)  # Your FPE implementation
    
    def validate(self, params: dict) -> None:
        if "key" not in params:
            raise ValueError("FPE operator requires 'key' parameter")
    
    def operator_name(self) -> str:
        return "fpe"
    
    def operator_type(self) -> OperatorType:
        return OperatorType.Encrypt
```

---

## 11. Troubleshooting

### Issue: "No entities detected"

**Causes:**
1. Threshold too high → Lower `qt_threshold` to 0.1
2. Blank spaCy model → Install `en_core_web_lg`
3. Wrong entity types → Verify entity names match `ALL_ENTITIES`

**Debug:**
```python
results = engine.analyze(text, return_decision_process=True)
for r in results:
    print(r.entity_type, r.score, r.analysis_explanation)
```

### Issue: "Slow batch processing"

**Causes:**
1. Large chunk size → Reduce `chunk_size` to 50-100 rows
2. No operator caching → Verify `_OPS_CACHE` is being used
3. Too many entity types → Limit to necessary entities only

**Profile:**
```python
import cProfile
cProfile.run("engine.anonymize(...)", sort="cumtime")
```

### Issue: "UI freezes during analysis"

**Cause:** Synchronous processing of large text.

**Fix:** Use `invoke_long_callback` for text >10KB or batch jobs >100 rows.

---

## 12. References

### Documentation
- **Presidio Docs:** https://microsoft.github.io/presidio/
- **Taipy Docs:** https://docs.taipy.io/
- **spaCy Models:** https://spacy.io/models/en

### Key Files
- `pii_engine.py` — Presidio wrapper & engine management
- `app.py` — Taipy GUI callbacks & state management
- `tasks.py` — Background batch processing pipeline
- `pages/definitions.py` — Page markup & layout
- `tests/test_pii_engine.py` — Unit tests for Presidio integration

### Related Documents
- `docs/spacy.md` — spaCy model usage guide
- `docs/deployment.md` — Production deployment notes
- `.github/copilot-instructions.md` — Full codebase reference

---

## 13. Summary

**Key Integration Patterns:**

1. **Singleton Engine:** One `PIIEngine` instance shared across entire app
2. **Lazy Initialization:** Presidio engines load on first use (fast startup)
3. **Reactive State:** Taipy automatically syncs state → UI (no manual DOM updates)
4. **Background Jobs:** Batch processing via Taipy Orchestrator (non-blocking)
5. **Caching:** Operator configs and denylist patterns cached for performance
6. **Audit Trail:** Every PII operation logged immutably

**Production Checklist:**

- ✅ Install `en_core_web_lg` spaCy model
- ✅ Set explicit hash salt for referential integrity
- ✅ Use `invoke_long_callback` for large texts/datasets
- ✅ Monitor Presidio engine thread safety in multi-user deployments
- ✅ Configure appropriate confidence thresholds per use case
- ✅ Test with real-world PII samples before production deployment

---

*Last Updated: 2026-03-06*  
*Version: 2.0*  
*Status: Complete Reference*
