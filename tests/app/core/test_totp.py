from __future__ import annotations

import base64
from unittest.mock import patch

import pyotp
import pytest

from app.core.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_qr_base64,
    generate_totp_secret,
    get_otpauth_uri,
    hash_backup_code,
    verify_totp,
)

_FERNET_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()


def _patch_settings():
    class _Cfg:
        totp_encryption_key = _FERNET_KEY

    return patch("app.core.totp.settings", _Cfg())


def test_generate_totp_secret_is_base32() -> None:
    secret = generate_totp_secret()

    base64.b32decode(secret, casefold=True)
    assert len(secret) >= 16


def test_encrypt_decrypt_roundtrip() -> None:
    with _patch_settings():
        plain = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_secret(plain)

        assert encrypted != plain
        assert decrypt_secret(encrypted) == plain


def test_encrypt_produces_different_ciphertexts() -> None:
    with _patch_settings():
        plain = "JBSWY3DPEHPK3PXP"
        a = encrypt_secret(plain)
        b = encrypt_secret(plain)

        assert a != b


def test_get_otpauth_uri_format() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    email = "user@example.com"

    uri = get_otpauth_uri(secret, email)

    assert uri.startswith("otpauth://totp/")
    assert "DotSound" in uri
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "user%40example.com" in uri


def test_generate_qr_base64_returns_png() -> None:
    uri = "otpauth://totp/DotSound:u@e.com?secret=A"

    result = generate_qr_base64(uri)

    raw = base64.b64decode(result)
    assert raw[:4] == b"\x89PNG"


def test_verify_totp_valid_code() -> None:
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    code = totp.now()

    assert verify_totp(secret, code) is True


def test_verify_totp_invalid_code() -> None:
    secret = pyotp.random_base32()

    assert verify_totp(secret, "000000") is False


def test_generate_backup_codes_count() -> None:
    codes = generate_backup_codes(5)

    assert len(codes) == 5
    assert all("-" in c for c in codes)


def test_generate_backup_codes_default_count() -> None:
    codes = generate_backup_codes()

    assert len(codes) == 8


def test_generate_backup_codes_uniqueness() -> None:
    codes = generate_backup_codes(20)

    assert len(set(codes)) == 20


def test_hash_backup_code_deterministic() -> None:
    code = "ABCD-EF12"

    assert hash_backup_code(code) == hash_backup_code(
        code
    )


def test_hash_backup_code_case_insensitive() -> None:
    assert hash_backup_code(
        "abcd-ef12"
    ) == hash_backup_code("ABCD-EF12")


def test_hash_backup_code_is_hex_sha256() -> None:
    result = hash_backup_code("TEST-CODE")

    assert len(result) == 64
    int(result, 16)
