"""JWT creation/verification and Telegram WebApp initData HMAC validation."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote

from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = "HS256"


class AuthError(Exception):
    """Raised when authentication or signature verification fails."""


def verify_telegram_init_data(init_data: str) -> dict[str, object]:
    """
    Validate Telegram WebApp initData HMAC-SHA256 signature.

    Returns parsed Telegram user dict on success.
    Raises AuthError on invalid/missing signature or missing user data.
    """
    parsed = parse_qs(unquote(init_data), keep_blank_values=True)

    hash_values = parsed.pop("hash", [])
    if not hash_values:
        raise AuthError("Missing hash in initData")
    received_hash = hash_values[0]

    data_check_string = "\n".join(
        sorted(f"{k}={v[0]}" for k, v in parsed.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        settings.telegram_bot_token.encode(),
        hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise AuthError("Invalid initData signature")

    user_json = parsed.get("user", [None])[0]
    if not user_json:
        raise AuthError("No user data in initData")

    return dict(json.loads(user_json))  # type: ignore[arg-type]


def create_access_token(user_id: int, is_admin: bool) -> str:
    """Create a signed JWT for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_expire_days
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "admin": is_admin,
        "exp": expire,
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM))


def decode_access_token(token: str) -> dict[str, object]:
    """
    Decode and verify a JWT.
    Raises AuthError on invalid or expired token.
    """
    try:
        return dict(  # type: ignore[arg-type]
            jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
        )
    except JWTError as exc:
        raise AuthError(str(exc)) from exc
