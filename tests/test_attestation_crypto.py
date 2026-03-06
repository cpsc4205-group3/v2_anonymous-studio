from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.attestation_crypto import (
    build_attestation_payload,
    sign_attestation_payload,
    verify_attestation_signature,
)


def _seed_b64_from_private_key(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(raw).decode("ascii")


def test_sign_attestation_payload_round_trip(monkeypatch):
    key = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ANON_ATTEST_SIGNING_KEY_B64", _seed_b64_from_private_key(key))
    monkeypatch.setenv("ANON_ATTEST_SIGNING_KEY_ID", "test-k1")

    payload = build_attestation_payload(
        card={
            "id": "card-1",
            "title": "HIPAA review",
            "description": "Validate redaction quality",
            "status": "review",
            "priority": "high",
            "labels": ["hipaa", "urgent"],
            "session_id": "sess-1",
            "scenario_id": "sc-1",
            "job_id": "job-1",
            "updated_at": "2026-03-05T18:07:00",
        },
        attested_by="Alex",
        attested_at="2026-03-05T18:08:00",
        attestation_note="Approved for release.",
        actor_sub="auth0|abc123",
        actor_name="Alex",
        actor_email="alex@example.com",
    )
    signed = sign_attestation_payload(payload)

    assert signed.signed is True
    assert signed.verified is True
    assert signed.algorithm == "ed25519"
    assert signed.key_id == "test-k1"
    assert bool(signed.signature_b64)
    assert bool(signed.public_key_b64)
    assert verify_attestation_signature(
        signed.payload_json,
        signed.signature_b64,
        signed.public_key_b64,
    )


def test_sign_attestation_payload_without_key_returns_unsigned(monkeypatch):
    for name in (
        "ANON_ATTEST_SIGNING_KEY_B64",
        "ANON_ATTEST_SIGNING_KEY_PEM",
        "ANON_ATTEST_SIGNING_KEY_FILE",
        "ANON_ATTEST_SIGNING_KEY_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    payload = build_attestation_payload(
        card={"id": "card-2", "title": "No key", "updated_at": "2026-03-05T18:07:00"},
        attested_by="Taylor",
        attested_at="2026-03-05T18:09:00",
        attestation_note="Unsigned for local dev",
    )
    signed = sign_attestation_payload(payload)

    assert signed.signed is False
    assert signed.verified is False
    assert signed.signature_b64 == ""
    assert "not configured" in signed.error.lower()
