"""Unit tests for commercial security, envelope encryption, and JWT authentication."""

import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    decrypt_secret,
    encrypt_secret,
    generate_api_key,
    verify_api_key,
)


def test_envelope_encryption_roundtrip():
    secret = "gho_super_secret_github_token_987654321"
    encrypted = encrypt_secret(secret)
    assert encrypted is not None
    assert encrypted != secret

    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret


def test_envelope_encryption_handles_none():
    assert encrypt_secret(None) is None
    assert decrypt_secret(None) is None


def test_envelope_encryption_invalid_token():
    assert decrypt_secret("invalid-corrupt-payload") is None


def test_jwt_access_token_lifecycle():
    payload = {"sub": "user_123", "email": "test@domain.com", "org_id": "org_456"}
    token = create_access_token(payload)
    assert isinstance(token, str)

    decoded = decode_jwt_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_123"
    assert decoded["email"] == "test@domain.com"
    assert decoded["org_id"] == "org_456"
    assert decoded["type"] == "access"


def test_jwt_refresh_token_lifecycle():
    token = create_refresh_token({"sub": "user_123"})
    decoded = decode_jwt_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_123"
    assert decoded["type"] == "refresh"


def test_jwt_invalid_token():
    assert decode_jwt_token("totally.bogus.token") is None


def test_api_key_generation_and_verification():
    raw_key, display_prefix, hashed_key = generate_api_key()
    assert raw_key.startswith("cs_live_")
    assert display_prefix.startswith("cs_live_")
    assert len(hashed_key) == 64  # SHA-256 hex string

    # Verification
    assert verify_api_key(raw_key, hashed_key) is True
    assert verify_api_key("cs_live_tampered_key_value", hashed_key) is False