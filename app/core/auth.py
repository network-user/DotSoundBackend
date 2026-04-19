from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import structlog
from dotsound_private_core.services.auth_policy import (
    AUTH_DATE_MAX_AGE,
)
from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = "HS256"
logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class AuthError(Exception):
    pass


def verify_telegram_init_data(
    init_data: str,
) -> dict[str, object]:
    """Validate Telegram WebApp initData via HMAC-SHA256."""
    parsed = parse_qs(
        init_data, keep_blank_values=True
    )

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

    if not hmac.compare_digest(
        computed_hash, received_hash
    ):
        logger.debug(
            "telegram_hmac_mismatch",
            computed=computed_hash,
            received=received_hash,
        )
        raise AuthError("Invalid initData signature")

    auth_date_str = parsed.get("auth_date", [None])[0]
    if auth_date_str:
        try:
            auth_ts = int(auth_date_str)
            now_ts = int(
                datetime.now(timezone.utc).timestamp()
            )
            max_age = AUTH_DATE_MAX_AGE
            if now_ts - auth_ts > max_age:
                raise AuthError(
                    "initData expired (auth_date too old)"
                )
        except ValueError:
            raise AuthError("Invalid auth_date")

    user_json = parsed.get("user", [None])[0]
    if not user_json:
        raise AuthError("No user data in initData")

    return dict(json.loads(user_json))  # type: ignore[arg-type]


def create_access_token(
    user_id: int, is_admin: bool
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_expire_days
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "admin": is_admin,
        "exp": expire,
    }
    return str(
        jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=_ALGORITHM,
        )
    )


def create_scoped_token(
    user_id: int,
    scope: str,
    ttl_minutes: int = 15,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ttl_minutes
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "scope": scope,
        "admin": False,
        "exp": expire,
    }
    return str(
        jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=_ALGORITHM,
        )
    )


def _admin_secret() -> str:
    secret = settings.admin_jwt_secret or settings.jwt_secret
    if not secret:
        raise AuthError("ADMIN_JWT_SECRET is not set")
    return secret


def create_admin_token(
    *,
    user_id: int,
    jti: str,
    device_id: int,
    ttl_seconds: int,
    scope: str = "admin",
    extra: dict[str, object] | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=ttl_seconds
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "scope": scope,
        "jti": jti,
        "device_id": device_id,
        "exp": expire,
    }
    if extra:
        payload.update(extra)
    return str(
        jwt.encode(
            payload,
            _admin_secret(),
            algorithm=_ALGORITHM,
        )
    )


def decode_admin_token(
    token: str,
) -> dict[str, object]:
    try:
        return dict(  # type: ignore[arg-type]
            jwt.decode(
                token,
                _admin_secret(),
                algorithms=[_ALGORITHM],
            )
        )
    except JWTError as exc:
        raise AuthError(str(exc)) from exc


def decode_access_token(
    token: str,
) -> dict[str, object]:
    try:
        return dict(  # type: ignore[arg-type]
            jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[_ALGORITHM],
            )
        )
    except JWTError as exc:
        raise AuthError(str(exc)) from exc
