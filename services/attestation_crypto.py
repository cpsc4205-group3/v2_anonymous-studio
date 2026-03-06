"""Digital signatures for compliance attestations.

This module provides a minimal, deterministic attestation signature flow:
- Build a canonical payload snapshot for an attested card.
- Hash payload with SHA-256.
- Sign payload bytes with Ed25519.
- Verify signatures for integrity checks.

Configuration:
- ANON_ATTEST_SIGNING_KEY_B64: base64 raw Ed25519 private key (32-byte seed)
  or base64 PKCS8 DER private key.
- ANON_ATTEST_SIGNING_KEY_PEM: inline PEM private key (supports "\\n" escapes).
- ANON_ATTEST_SIGNING_KEY_FILE: filesystem path to a PEM/DER private key.
- ANON_ATTEST_SIGNING_KEY_ID: optional key identifier; defaults to pubkey SHA-256 prefix.
- ANON_ATTEST_REQUIRE_SIGNATURE: if truthy, callers should reject unsigned attestation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def signature_required() -> bool:
    return _truthy_env("ANON_ATTEST_REQUIRE_SIGNATURE", default=False)


def _b64decode(raw: str) -> bytes:
    s = (raw or "").strip()
    if not s:
        return b""
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad)


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _payload_hash_hex(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _load_private_key_from_bytes(raw: bytes) -> Ed25519PrivateKey:
    if len(raw) == 32:
        return Ed25519PrivateKey.from_private_bytes(raw)
    key = serialization.load_der_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Private key is not Ed25519.")
    return key


def _read_private_key() -> tuple[Optional[Ed25519PrivateKey], str]:
    key_file = (os.environ.get("ANON_ATTEST_SIGNING_KEY_FILE", "") or "").strip()
    if key_file:
        with open(key_file, "rb") as fh:
            key_bytes = fh.read()
        try:
            key = serialization.load_pem_private_key(key_bytes, password=None)
        except Exception:
            key = serialization.load_der_private_key(key_bytes, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            return None, "Configured private key is not Ed25519."
        return key, ""

    key_pem = (os.environ.get("ANON_ATTEST_SIGNING_KEY_PEM", "") or "").strip()
    if key_pem:
        pem_bytes = key_pem.replace("\\n", "\n").encode("utf-8")
        key = serialization.load_pem_private_key(pem_bytes, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            return None, "Configured private key is not Ed25519."
        return key, ""

    key_b64 = (os.environ.get("ANON_ATTEST_SIGNING_KEY_B64", "") or "").strip()
    if key_b64:
        try:
            key = _load_private_key_from_bytes(_b64decode(key_b64))
        except Exception as ex:  # pragma: no cover - defensive for malformed keys
            return None, f"Invalid ANON_ATTEST_SIGNING_KEY_B64: {ex}"
        return key, ""

    return None, "Signing key is not configured."


def _public_key_raw_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _key_id_for_public_key(public_key_raw: bytes) -> str:
    override = (os.environ.get("ANON_ATTEST_SIGNING_KEY_ID", "") or "").strip()
    if override:
        return override
    return hashlib.sha256(public_key_raw).hexdigest()[:16]


def _normalize_labels(value: Any) -> list[str]:
    if not value:
        return []
    labels = [str(v).strip() for v in list(value) if str(v).strip()]
    return sorted(set(labels))


def _get_field(card: Any, name: str, default: Any = "") -> Any:
    if isinstance(card, Mapping):
        return card.get(name, default)
    return getattr(card, name, default)


def build_attestation_payload(
    *,
    card: Any,
    attested_by: str,
    attested_at: str,
    attestation_note: str,
    actor_sub: str = "",
    actor_name: str = "",
    actor_email: str = "",
) -> dict[str, Any]:
    """Build canonical attestation payload from card snapshot and actor metadata."""
    card_snapshot = {
        "id": str(_get_field(card, "id", "")),
        "title": str(_get_field(card, "title", "")),
        "description": str(_get_field(card, "description", "")),
        "status": str(_get_field(card, "status", "")),
        "priority": str(_get_field(card, "priority", "")),
        "labels": _normalize_labels(_get_field(card, "labels", [])),
        "session_id": str(_get_field(card, "session_id", "") or ""),
        "scenario_id": str(_get_field(card, "scenario_id", "") or ""),
        "job_id": str(_get_field(card, "job_id", "") or ""),
        "updated_at": str(_get_field(card, "updated_at", "") or ""),
    }
    actor = {
        "sub": str(actor_sub or ""),
        "name": str(actor_name or ""),
        "email": str(actor_email or ""),
    }
    return {
        "schema": "anonymous-studio.attestation.v1",
        "attested_at": str(attested_at or ""),
        "attested_by": str(attested_by or ""),
        "attestation_note": str(attestation_note or ""),
        "card": card_snapshot,
        "actor": actor,
    }


@dataclass(frozen=True)
class AttestationSignatureBundle:
    payload_json: str
    payload_hash: str
    signature_b64: str
    algorithm: str
    key_id: str
    public_key_b64: str
    verified: bool
    signed: bool
    error: str = ""


def sign_attestation_payload(payload: Mapping[str, Any]) -> AttestationSignatureBundle:
    payload_json = _canonical_json(payload)
    payload_hash = _payload_hash_hex(payload_json)

    private_key, key_err = _read_private_key()
    if private_key is None:
        return AttestationSignatureBundle(
            payload_json=payload_json,
            payload_hash=payload_hash,
            signature_b64="",
            algorithm="ed25519",
            key_id="",
            public_key_b64="",
            verified=False,
            signed=False,
            error=key_err,
        )

    payload_bytes = payload_json.encode("utf-8")
    signature_raw = private_key.sign(payload_bytes)
    public_key_raw = _public_key_raw_bytes(private_key)
    key_id = _key_id_for_public_key(public_key_raw)
    signature_b64 = _b64encode(signature_raw)
    public_key_b64 = _b64encode(public_key_raw)
    verified = verify_attestation_signature(payload_json, signature_b64, public_key_b64)
    return AttestationSignatureBundle(
        payload_json=payload_json,
        payload_hash=payload_hash,
        signature_b64=signature_b64,
        algorithm="ed25519",
        key_id=key_id,
        public_key_b64=public_key_b64,
        verified=verified,
        signed=True,
        error="",
    )


def verify_attestation_signature(
    payload_json: str,
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    if not payload_json or not signature_b64 or not public_key_b64:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_b64decode(public_key_b64))
        public_key.verify(_b64decode(signature_b64), payload_json.encode("utf-8"))
        return True
    except Exception:
        return False
