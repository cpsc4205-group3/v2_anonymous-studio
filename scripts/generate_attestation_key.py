#!/usr/bin/env python3
"""Generate Ed25519 attestation signing keys for Anonymous Studio."""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def main() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public_raw).hexdigest()[:16]

    print("# Add these to .env (keep private key secret):")
    print(f"ANON_ATTEST_SIGNING_KEY_B64={_b64(private_raw)}")
    print(f"ANON_ATTEST_SIGNING_KEY_ID={key_id}")
    print("ANON_ATTEST_REQUIRE_SIGNATURE=1")
    print()
    print("# Optional verification-only value:")
    print(f"# Public key (base64 raw): {_b64(public_raw)}")


if __name__ == "__main__":
    main()
