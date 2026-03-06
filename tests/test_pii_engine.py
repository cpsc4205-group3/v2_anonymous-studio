"""
Tests for pii_engine.py — PII detection, anonymization, and display utilities.

Run:
    pytest tests/test_pii_engine.py -v

These tests focus on correctness of entity catalogue, operator configuration,
and display helpers — they do NOT require the full Presidio/spaCy stack
(highlight_md and entity catalogue tests are pure-Python).

For tests that do require the engine (anonymize/analyze), pytest.importorskip
is used so the suite still runs cleanly in restricted environments without
the NLP models installed.
"""
from __future__ import annotations
import pytest


# ── Entity catalogue ──────────────────────────────────────────────────────────

def test_all_entities_contains_organization():
    """Regression: ORGANIZATION was mapped by spaCy NLP config but absent from
    ALL_ENTITIES, causing it to be silently dropped by Presidio."""
    from pii_engine import ALL_ENTITIES
    assert "ORGANIZATION" in ALL_ENTITIES


def test_all_entities_no_duplicates():
    from pii_engine import ALL_ENTITIES
    assert len(ALL_ENTITIES) == len(set(ALL_ENTITIES))


def test_entity_colors_covers_all_entities():
    """Every entity in ALL_ENTITIES must have a display colour."""
    from pii_engine import ALL_ENTITIES, ENTITY_COLORS
    missing = [e for e in ALL_ENTITIES if e not in ENTITY_COLORS]
    assert missing == [], f"Missing colors for: {missing}"


def test_operators_list():
    from pii_engine import OPERATORS
    assert set(OPERATORS) >= {"replace", "redact", "mask", "hash"}


def test_spacy_model_options_include_auto_and_blank():
    from pii_engine import get_spacy_model_options
    options = get_spacy_model_options()
    assert "auto" in options
    assert "blank" in options


# ── highlight_md XSS fixes ────────────────────────────────────────────────────

def test_highlight_md_no_entities_returns_no_pii_message():
    from pii_engine import highlight_md
    result = highlight_md("Hello world", [])
    assert "No PII detected" in result


def test_highlight_md_escapes_html_in_plain_segments():
    """Regression: user text like <script>alert(1)</script> was passed through
    unescaped into the Markdown output."""
    from pii_engine import highlight_md
    # Entity at start — plain text follows after cursor
    entities = [{"start": 0, "end": 5, "entity_type": "PERSON",
                 "score": 0.9, "text": "Alice"}]
    evil_suffix = " <script>alert(1)</script>"
    text = "Alice" + evil_suffix
    result = highlight_md(text, entities)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_highlight_md_escapes_html_before_first_entity():
    from pii_engine import highlight_md
    entities = [{"start": 20, "end": 25, "entity_type": "EMAIL_ADDRESS",
                 "score": 0.9, "text": "email"}]
    text = "<b>Dangerous prefix</b>email"
    result = highlight_md(text, entities)
    # The <b> tags in the prefix should be escaped
    assert "<b>" not in result
    assert "&lt;b&gt;" in result


def test_highlight_md_formats_entity_span():
    from pii_engine import highlight_md
    entities = [{"start": 0, "end": 5, "entity_type": "PERSON",
                 "score": 0.85, "text": "Alice"}]
    result = highlight_md("Alice is here", entities)
    # Entity appears in inline-code span with label and confidence
    assert "`Alice`" in result
    assert "Person" in result
    assert "85%" in result


def test_highlight_md_merges_overlapping_entities_keeps_higher_score():
    from pii_engine import highlight_md
    # Overlapping: [0,10] score=0.7 and [2,8] score=0.9 → keep score=0.9
    entities = [
        {"start": 0, "end": 10, "entity_type": "PERSON", "score": 0.70, "text": "Alice Bob"},
        {"start": 2, "end": 8,  "entity_type": "EMAIL_ADDRESS", "score": 0.90, "text": "ice Bo"},
    ]
    result = highlight_md("Alice Bob here", entities)
    assert "Email Address" in result  # higher-score entity wins
    assert "Person" not in result


# ── Detection rationale helpers (pure-Python, no NLP stack required) ──────────

class _MockExplanation:
    """Minimal stand-in for Presidio AnalysisExplanation."""
    def __init__(self, recognizer="", pattern_name="", original_score=None,
                 textual_explanation=""):
        self.recognizer = recognizer
        self.pattern_name = pattern_name
        self.original_score = original_score
        self.textual_explanation = textual_explanation


class _MockResult:
    """Minimal stand-in for Presidio RecognizerResult."""
    def __init__(self, entity_type, start, end, score, explanation=None):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score
        self.analysis_explanation = explanation


def test_build_rationale_no_explanation_returns_empty():
    """When Presidio returns no analysis_explanation the rationale is empty."""
    from pii_engine import PIIEngine
    r = _MockResult("EMAIL_ADDRESS", 0, 15, 0.85, explanation=None)
    assert PIIEngine._build_rationale(r) == ""


def test_build_rationale_with_recognizer():
    """Recognizer name appears in the rationale string."""
    from pii_engine import PIIEngine
    ex = _MockExplanation(recognizer="EmailRecognizer")
    r = _MockResult("EMAIL_ADDRESS", 0, 15, 0.85, explanation=ex)
    assert "EmailRecognizer" in PIIEngine._build_rationale(r)


def test_build_rationale_with_pattern_name():
    """Pattern name is included when present."""
    from pii_engine import PIIEngine
    ex = _MockExplanation(recognizer="EmailRecognizer", pattern_name="email_regex")
    r = _MockResult("EMAIL_ADDRESS", 0, 15, 0.85, explanation=ex)
    result = PIIEngine._build_rationale(r)
    assert "pattern=email_regex" in result


def test_build_rationale_includes_textual_explanation():
    """Human-readable textual_explanation is appended."""
    from pii_engine import PIIEngine
    ex = _MockExplanation(recognizer="PhoneRecognizer",
                          textual_explanation="Matched US phone pattern")
    r = _MockResult("PHONE_NUMBER", 0, 12, 0.75, explanation=ex)
    assert "Matched US phone pattern" in PIIEngine._build_rationale(r)


def test_build_rationale_omits_redundant_original_score():
    """raw_score is omitted when original_score equals the final score."""
    from pii_engine import PIIEngine
    ex = _MockExplanation(recognizer="Rec", original_score=0.85)
    r = _MockResult("PERSON", 0, 5, 0.85, explanation=ex)
    assert "raw_score" not in PIIEngine._build_rationale(r)


def test_build_rationale_shows_raw_score_when_boosted():
    """raw_score appears when context boosted the score above the original."""
    from pii_engine import PIIEngine
    ex = _MockExplanation(recognizer="Rec", original_score=0.60)
    r = _MockResult("PERSON", 0, 5, 0.85, explanation=ex)
    assert "raw_score=0.60" in PIIEngine._build_rationale(r)


def test_entity_dict_includes_rationale_and_recognizer_keys():
    """_entity_dict must always return 'rationale' and 'recognizer' keys."""
    from pii_engine import PIIEngine
    ex = _MockExplanation(recognizer="EmailRecognizer", pattern_name="email")
    r = _MockResult("EMAIL_ADDRESS", 9, 24, 0.9, explanation=ex)
    d = PIIEngine._entity_dict(r, "Contact: alice@test.com")
    assert "rationale" in d
    assert "recognizer" in d
    assert d["recognizer"] == "EmailRecognizer"


def test_entity_dict_text_extraction():
    """_entity_dict extracts the matched text span from the source string."""
    from pii_engine import PIIEngine
    r = _MockResult("EMAIL_ADDRESS", 9, 23, 0.9, explanation=None)
    d = PIIEngine._entity_dict(r, "Contact: alice@test.com here")
    assert d["text"] == "alice@test.com"


def test_entity_dict_rationale_empty_without_explanation():
    from pii_engine import PIIEngine
    r = _MockResult("CREDIT_CARD", 0, 16, 0.95, explanation=None)
    d = PIIEngine._entity_dict(r, "4111111111111111")
    assert d["rationale"] == ""
    assert d["recognizer"] == ""


# ── PIIEngine (requires presidio + spacy) ─────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    """Load PIIEngine once per module — expensive but necessary."""
    try:
        from pii_engine import PIIEngine
        return PIIEngine()
    except Exception as e:
        pytest.skip(f"PIIEngine unavailable: {e}")


def test_engine_analyzes_email(engine):
    results = engine.analyze("Contact us at test@example.com for help.")
    types = [r["entity_type"] for r in results]
    assert "EMAIL_ADDRESS" in types


def test_engine_analyzes_phone(engine):
    results = engine.analyze("Call me at 555-867-5309.")
    types = [r["entity_type"] for r in results]
    assert "PHONE_NUMBER" in types


def test_engine_replace_operator(engine):
    result = engine.anonymize("Email: bob@example.com", ["EMAIL_ADDRESS"], "replace")
    assert "<EMAIL_ADDRESS>" in result.anonymized_text
    assert "bob@example.com" not in result.anonymized_text


def test_engine_redact_operator(engine):
    result = engine.anonymize("Email: bob@example.com", ["EMAIL_ADDRESS"], "redact")
    assert "bob@example.com" not in result.anonymized_text


def test_engine_mask_operator(engine):
    result = engine.anonymize("Email: bob@example.com", ["EMAIL_ADDRESS"], "mask")
    assert "*" in result.anonymized_text
    assert "bob@example.com" not in result.anonymized_text


def test_engine_hash_operator_consistent(engine):
    """Hash with fixed salt must produce identical output for identical input."""
    r1 = engine.anonymize("SSN: 123-45-6789", ["US_SSN"], "hash")
    r2 = engine.anonymize("SSN: 123-45-6789", ["US_SSN"], "hash")
    assert r1.anonymized_text == r2.anonymized_text


def test_engine_hash_operator_different_inputs_differ(engine):
    r1 = engine.anonymize("SSN: 123-45-6789", ["US_SSN"], "hash")
    r2 = engine.anonymize("SSN: 987-65-4321", ["US_SSN"], "hash")
    assert r1.anonymized_text != r2.anonymized_text


def test_engine_entity_counts_in_result(engine):
    result = engine.anonymize(
        "bob@example.com and alice@example.com", ["EMAIL_ADDRESS"], "replace")
    assert result.entity_counts.get("EMAIL_ADDRESS", 0) == 2


def test_engine_empty_text_returns_safely(engine):
    result = engine.anonymize("", ["EMAIL_ADDRESS"], "replace")
    assert result.anonymized_text == ""
    assert result.entity_counts == {}


# ── Entity type filtering ─────────────────────────────────────────────────────

def test_analyze_with_entity_subset_returns_only_selected_types(engine):
    """When a specific entity list is provided, only those types are returned."""
    text = "Email bob@example.com or call 555-867-5309"
    results = engine.analyze(text, entities=["EMAIL_ADDRESS"])
    types = {r["entity_type"] for r in results}
    assert "EMAIL_ADDRESS" in types
    assert "PHONE_NUMBER" not in types


def test_analyze_default_entities_returns_all_types(engine):
    """When no entity list is given, all supported entities are candidates."""
    from pii_engine import ALL_ENTITIES
    text = "Email bob@example.com or call 555-867-5309"
    results = engine.analyze(text)
    types = {r["entity_type"] for r in results}
    # At least one of the two entity types must appear without restriction
    assert types.issubset(set(ALL_ENTITIES)), "Returned types must all be in ALL_ENTITIES"
    assert len(types) >= 1


def test_analyze_empty_entity_list_falls_back_to_all_entities(engine):
    """Passing None for entities falls back to the full ALL_ENTITIES catalogue."""
    from pii_engine import ALL_ENTITIES
    text = "Email bob@example.com"
    results_default = engine.analyze(text)
    results_none = engine.analyze(text, entities=None)
    # Both should produce the same results
    assert [r["entity_type"] for r in results_default] == [r["entity_type"] for r in results_none]


def test_analyze_single_entity_type_excludes_others(engine):
    """Selecting a single entity type must exclude all other detected types."""
    text = "SSN 123-45-6789 and email test@example.com"
    results = engine.analyze(text, entities=["US_SSN"])
    types = {r["entity_type"] for r in results}
    assert types <= {"US_SSN"}, f"Expected only US_SSN but got {types}"
def test_analyze_results_contain_rationale_key(engine):
    """Every entity dict returned by analyze() must expose a 'rationale' key
    so the entity-evidence table can display detection explanations."""
    results = engine.analyze("Contact us at test@example.com for help.",
                             entities=["EMAIL_ADDRESS"])
    assert results, "Expected at least one entity for a known email address"
    for r in results:
        assert "rationale" in r, f"Missing 'rationale' key in entity dict: {r}"
        assert "recognizer" in r, f"Missing 'recognizer' key in entity dict: {r}"


def test_analyze_results_rationale_is_string(engine):
    """The 'rationale' value must be a plain string (never None)."""
    results = engine.analyze("My SSN is 123-45-6789.", entities=["US_SSN"])
    for r in results:
        assert isinstance(r["rationale"], str), (
            f"rationale should be str, got {type(r['rationale'])}"
        )
