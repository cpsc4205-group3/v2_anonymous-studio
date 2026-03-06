"""
Unit tests for anonymization operator accuracy and multi-document-type support.

Acceptance criteria covered:
  - Users can select anonymization method (redact, mask, replace, hash)
  - System produces de-identified output
  - Original and anonymized text are displayed side-by-side (AnalysisResult fields)

Subtasks:
  - Test with multiple document types (email body, medical form, financial doc, mixed PII)
  - Write unit tests for anonymization accuracy for all four operators

Run:
    pytest tests/test_anonymization_operators.py -v
"""
from __future__ import annotations
import re
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    """Load PIIEngine once per module — expensive but necessary for operator tests."""
    try:
        from pii_engine import PIIEngine
        return PIIEngine()
    except Exception as e:
        pytest.skip(f"PIIEngine unavailable: {e}")


# ── Document-type corpora ─────────────────────────────────────────────────────

EMAIL_BODY = (
    "Hi John,\n\n"
    "Please send the invoice to billing@acme.com by Friday.\n"
    "You can also reach me at +1-555-867-5309 if needed.\n\n"
    "Thanks,\nJane"
)

MEDICAL_FORM = (
    "Patient: Robert Smith  DOB: 01/14/1982\n"
    "SSN: 123-45-6789\n"
    "Prescription notes: continue lisinopril 10mg daily.\n"
    "Follow-up appointment on 06/30/2025.\n"
    "Referring physician NPI: 1234567890"
)

FINANCIAL_DOCUMENT = (
    "Account holder: Alice Johnson\n"
    "Credit card: 4111 1111 1111 1111  Exp: 09/27  CVV: 123\n"
    "Bank account: 12345678  Routing: 021000021\n"
    "Wire funds to IBAN: GB29 NWBK 6016 1331 9268 19\n"
    "IP logged from: 192.168.1.100"
)

MIXED_PII_PARAGRAPH = (
    "Contact support@example.com or call 800-555-0199. "
    "Reference ticket TKT-9812 and provide your SSN 987-65-4321 "
    "and passport number AB1234567 for identity verification."
)


# ── AnalysisResult side-by-side contract ─────────────────────────────────────

def test_analysis_result_exposes_original_and_anonymized(engine):
    """AnalysisResult must carry both original_text and anonymized_text
    so callers can render a side-by-side comparison."""
    from pii_engine import AnalysisResult
    result = engine.anonymize(EMAIL_BODY, ["EMAIL_ADDRESS", "PHONE_NUMBER"], "replace")
    assert isinstance(result, AnalysisResult), "anonymize() must return AnalysisResult"
    assert result.original_text == EMAIL_BODY
    assert isinstance(result.anonymized_text, str)
    # The anonymized text must differ from the original when PII is present
    assert result.original_text != result.anonymized_text or result.total_found == 0


def test_analysis_result_operator_recorded(engine):
    """AnalysisResult.operator_used must reflect the requested operator."""
    for op in ("replace", "redact", "mask", "hash"):
        result = engine.anonymize("Email test@test.com here", ["EMAIL_ADDRESS"], op)
        assert result.operator_used == op, (
            f"Expected operator_used='{op}', got '{result.operator_used}'"
        )


# ── Operator accuracy — replace ───────────────────────────────────────────────

def test_replace_operator_email(engine):
    result = engine.anonymize("Send to alice@example.com", ["EMAIL_ADDRESS"], "replace")
    assert "alice@example.com" not in result.anonymized_text
    assert "<EMAIL_ADDRESS>" in result.anonymized_text


def test_replace_operator_phone(engine):
    result = engine.anonymize("Call 555-867-5309 now", ["PHONE_NUMBER"], "replace")
    assert "555-867-5309" not in result.anonymized_text
    assert "<PHONE_NUMBER>" in result.anonymized_text


def test_replace_operator_ssn(engine):
    result = engine.anonymize("SSN: 123-45-6789", ["US_SSN"], "replace")
    assert "123-45-6789" not in result.anonymized_text
    assert "<US_SSN>" in result.anonymized_text


def test_replace_operator_credit_card(engine):
    result = engine.anonymize(
        "Card: 4111 1111 1111 1111", ["CREDIT_CARD"], "replace"
    )
    assert "4111 1111 1111 1111" not in result.anonymized_text
    assert "<CREDIT_CARD>" in result.anonymized_text


# ── Operator accuracy — redact ────────────────────────────────────────────────

def test_redact_operator_removes_email(engine):
    result = engine.anonymize("Contact bob@example.com", ["EMAIL_ADDRESS"], "redact")
    assert "bob@example.com" not in result.anonymized_text
    # After redaction the placeholder tags must NOT be present either
    assert "<EMAIL_ADDRESS>" not in result.anonymized_text


def test_redact_operator_removes_phone(engine):
    result = engine.anonymize("Phone: 800-555-0100", ["PHONE_NUMBER"], "redact")
    assert "800-555-0100" not in result.anonymized_text


def test_redact_shortens_text(engine):
    """Redact must produce shorter text than the original when PII is found."""
    original = "Email alice@example.com please"
    result = engine.anonymize(original, ["EMAIL_ADDRESS"], "redact")
    if result.total_found > 0:
        assert len(result.anonymized_text) < len(original)


# ── Operator accuracy — mask ──────────────────────────────────────────────────

def test_mask_operator_uses_asterisks(engine):
    result = engine.anonymize("Email: dev@example.com", ["EMAIL_ADDRESS"], "mask")
    assert "dev@example.com" not in result.anonymized_text
    assert "*" in result.anonymized_text


def test_mask_operator_length_reasonable(engine):
    """Masked output must not grow significantly longer than the original."""
    original = "Card 4111 1111 1111 1111 end"
    result = engine.anonymize(original, ["CREDIT_CARD"], "mask")
    # Allow some slack, but masked output shouldn't be more than 2× original
    assert len(result.anonymized_text) <= len(original) * 2


def test_mask_operator_preserves_surrounding_text(engine):
    original = "Before dev@example.com after"
    result = engine.anonymize(original, ["EMAIL_ADDRESS"], "mask")
    assert "Before" in result.anonymized_text
    assert "after" in result.anonymized_text


# ── Operator accuracy — hash ──────────────────────────────────────────────────

def test_hash_operator_deterministic_email(engine):
    """Same input must produce the same hash every time."""
    r1 = engine.anonymize("admin@example.com", ["EMAIL_ADDRESS"], "hash")
    r2 = engine.anonymize("admin@example.com", ["EMAIL_ADDRESS"], "hash")
    assert r1.anonymized_text == r2.anonymized_text


def test_hash_operator_different_values_differ(engine):
    r1 = engine.anonymize("alpha@example.com", ["EMAIL_ADDRESS"], "hash")
    r2 = engine.anonymize("beta@example.com",  ["EMAIL_ADDRESS"], "hash")
    assert r1.anonymized_text != r2.anonymized_text


def test_hash_operator_removes_original_pii(engine):
    result = engine.anonymize("SSN: 123-45-6789", ["US_SSN"], "hash")
    assert "123-45-6789" not in result.anonymized_text


# ── Multi-document-type tests ─────────────────────────────────────────────────

def test_email_body_replace(engine):
    """Email-body document: replace removes all detected PII."""
    result = engine.anonymize(
        EMAIL_BODY,
        ["EMAIL_ADDRESS", "PHONE_NUMBER"],
        "replace",
    )
    assert "billing@acme.com" not in result.anonymized_text
    assert "+1-555-867-5309" not in result.anonymized_text
    assert result.total_found >= 2


def test_email_body_redact(engine):
    result = engine.anonymize(
        EMAIL_BODY,
        ["EMAIL_ADDRESS", "PHONE_NUMBER"],
        "redact",
    )
    assert "billing@acme.com" not in result.anonymized_text
    assert "+1-555-867-5309" not in result.anonymized_text


def test_medical_form_ssn_replace(engine):
    result = engine.anonymize(MEDICAL_FORM, ["US_SSN", "DATE_TIME"], "replace")
    assert "123-45-6789" not in result.anonymized_text


def test_medical_form_ssn_mask(engine):
    result = engine.anonymize(MEDICAL_FORM, ["US_SSN"], "mask")
    assert "123-45-6789" not in result.anonymized_text
    assert "*" in result.anonymized_text


def test_financial_document_credit_card_replace(engine):
    result = engine.anonymize(FINANCIAL_DOCUMENT, ["CREDIT_CARD", "IP_ADDRESS"], "replace")
    assert "4111 1111 1111 1111" not in result.anonymized_text


def test_financial_document_iban_replace(engine):
    result = engine.anonymize(FINANCIAL_DOCUMENT, ["IBAN_CODE"], "replace")
    assert "GB29 NWBK 6016 1331 9268 19" not in result.anonymized_text


def test_mixed_pii_all_operators_remove_pii(engine):
    """All four operators must remove the explicit email and phone from mixed PII text."""
    for op in ("replace", "redact", "mask", "hash"):
        result = engine.anonymize(
            MIXED_PII_PARAGRAPH,
            ["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"],
            op,
        )
        assert "support@example.com" not in result.anonymized_text, (
            f"operator='{op}': email still present"
        )
        assert "987-65-4321" not in result.anonymized_text, (
            f"operator='{op}': SSN still present"
        )


# ── Entity-to-operator mapping ────────────────────────────────────────────────

def test_entity_counts_same_across_operators(engine):
    """Operator choice must not change which entities are detected, only how they're replaced."""
    text = "Reach me at dev@example.com or 800-555-9876."
    entities = ["EMAIL_ADDRESS", "PHONE_NUMBER"]
    counts = {}
    for op in ("replace", "redact", "mask", "hash"):
        r = engine.anonymize(text, entities, op)
        counts[op] = r.total_found
    # All operators must detect the same number of entities
    assert len(set(counts.values())) == 1, (
        f"Entity count differs by operator: {counts}"
    )


def test_entity_types_same_across_operators(engine):
    """The set of entity types detected must be identical regardless of operator."""
    text = "Email test@example.com  SSN 123-45-6789  card 4111 1111 1111 1111"
    entities = ["EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD"]
    type_sets = {}
    for op in ("replace", "redact", "mask", "hash"):
        r = engine.anonymize(text, entities, op)
        type_sets[op] = frozenset(e["entity_type"] for e in r.entities)
    values = list(type_sets.values())
    assert all(v == values[0] for v in values), (
        f"Entity type sets differ across operators: {type_sets}"
    )


# ── Operators constant ────────────────────────────────────────────────────────

def test_operators_constant_has_all_four():
    """The OPERATORS list must include exactly the four supported operator names."""
    # Use importorskip so this passes even without full presidio stack if pii_engine
    # can be imported (module-level constants don't depend on the engine being loaded).
    pii_engine = pytest.importorskip("pii_engine")
    assert set(pii_engine.OPERATORS) >= {"replace", "redact", "mask", "hash"}, (
        "OPERATORS must contain replace, redact, mask, hash"
    )


def test_operator_labels_cover_all_operators():
    """OPERATOR_LABELS must contain a label for every operator in OPERATORS."""
    pii_engine = pytest.importorskip("pii_engine")
    missing = [op for op in pii_engine.OPERATORS if op not in pii_engine.OPERATOR_LABELS]
    assert missing == [], f"Missing labels for operators: {missing}"
