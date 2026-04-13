from __future__ import annotations

import base64
import hashlib
import io
import secrets

import pyotp
import qrcode  # type: ignore[import-untyped]
from cryptography.fernet import Fernet
from dotsound_private_core.services.auth_policy import (
    BACKUP_CODE_COUNT,
    TOTP_VALID_WINDOW,
)

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.totp_encryption_key
    if not key:
        raise RuntimeError(
            "TOTP_ENCRYPTION_KEY is not configured"
        )
    raw = base64.urlsafe_b64decode(key + "==")
    fernet_key = base64.urlsafe_b64encode(raw[:32])
    return Fernet(fernet_key)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(plain: str) -> str:
    return _get_fernet().encrypt(
        plain.encode()
    ).decode()


def decrypt_secret(encrypted: str) -> str:
    return _get_fernet().decrypt(
        encrypted.encode()
    ).decode()


def get_otpauth_uri(
    secret: str, email: str
) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=email, issuer_name="DotSound"
    )


def generate_qr_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(
        buf.getvalue()
    ).decode()


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(
        code, valid_window=TOTP_VALID_WINDOW
    )


def generate_backup_codes(
    count: int = BACKUP_CODE_COUNT,
) -> list[str]:
    return [
        f"{secrets.token_hex(2).upper()}"
        f"-{secrets.token_hex(2).upper()}"
        for _ in range(count)
    ]


def hash_backup_code(code: str) -> str:
    return hashlib.sha256(
        code.upper().encode()
    ).hexdigest()
