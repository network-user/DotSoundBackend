from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import (
    _ALGORITHM,
    create_access_token,
)
from dotsound_private_core.services.abuse import (
    is_disposable_email,
)
from dotsound_private_core.services.auth_policy import (
    FALLBACK_CODE_TTL,
    FALLBACK_COOLDOWN_TTL,
    FALLBACK_PREFIX,
    FALLBACK_RATE_TTL,
    should_burn_code,
    should_cooldown_account,
)
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
from app.models.user import User
from app.services.email_sender import (
    send_magic_link,
    send_totp_fallback_code,
)
from app.services.user_service import UserService

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)

_MAGIC_LINK_TYPE = "magic_link"
_2FA_SESSION_TYPE = "2fa_session"
_ML_PREFIX = "magic_link:"
_2FA_PREFIX = "2fa_session:"
_2FA_SESSION_TTL = 300


class EmailAuthError(Exception):
    pass


async def _get_redis() -> Any:
    import redis.asyncio as aioredis

    return aioredis.from_url(settings.redis_url)


def _create_magic_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.magic_link_ttl_minutes,
    )
    payload: dict[str, object] = {
        "sub": email.lower().strip(),
        "type": _MAGIC_LINK_TYPE,
        "exp": expire,
        "jti": secrets.token_hex(16),
    }
    return str(
        jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=_ALGORITHM,
        )
    )


def _decode_magic_token(
    token: str,
) -> dict[str, object]:
    try:
        payload = dict(
            jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[_ALGORITHM],
            )
        )
    except JWTError as exc:
        raise EmailAuthError(
            "Invalid or expired token"
        ) from exc
    if payload.get("type") != _MAGIC_LINK_TYPE:
        raise EmailAuthError("Invalid token type")
    return payload  # type: ignore[return-value]


def _create_2fa_session_token(
    user_id: int,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=_2FA_SESSION_TTL,
    )
    payload: dict[str, object] = {
        "sub": str(user_id),
        "type": _2FA_SESSION_TYPE,
        "exp": expire,
        "jti": secrets.token_hex(16),
    }
    return str(
        jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=_ALGORITHM,
        )
    )


def _decode_2fa_session_token(
    token: str,
) -> dict[str, object]:
    try:
        payload = dict(
            jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[_ALGORITHM],
            )
        )
    except JWTError as exc:
        raise EmailAuthError(
            "Invalid or expired 2FA session"
        ) from exc
    if payload.get("type") != _2FA_SESSION_TYPE:
        raise EmailAuthError(
            "Invalid session token type"
        )
    return payload  # type: ignore[return-value]


async def request_magic_link(
    email: str,
) -> None:
    normalized = email.lower().strip()

    if is_disposable_email(normalized):
        logger.warning(
            "disposable_email_blocked",
            email=normalized,
        )
        return

    token = _create_magic_token(normalized)
    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    redis = await _get_redis()
    await redis.setex(
        f"{_ML_PREFIX}{token_hash}",
        settings.magic_link_ttl_minutes * 60,
        normalized,
    )
    await redis.aclose()

    base_url = settings.mini_app_url
    if not base_url.endswith("/"):
        base_url += "/"
    link = f"{base_url}?token={token}"

    await send_magic_link(normalized, link)


async def verify_magic_link(
    token: str,
    session: AsyncSession,
) -> dict[str, object]:
    payload = _decode_magic_token(token)
    email = str(payload["sub"])
    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    redis = await _get_redis()
    key = f"{_ML_PREFIX}{token_hash}"
    stored = await redis.get(key)
    if not stored:
        await redis.aclose()
        raise EmailAuthError(
            "Token already used or expired"
        )
    await redis.delete(key)
    await redis.aclose()

    service = UserService(session)
    user, created = (
        await service.get_or_create_by_email(email)
    )

    if not user.is_active:
        raise EmailAuthError(
            "Account is deactivated"
        )

    if user.totp_enabled:
        session_token = _create_2fa_session_token(
            user.id
        )
        return {
            "requires_2fa": True,
            "session_token": session_token,
            "user_id": user.id,
        }

    access_token = create_access_token(
        user.id, user.is_admin
    )
    return {
        "requires_2fa": False,
        "access_token": access_token,
        "user_id": user.id,
        "is_admin": user.is_admin,
    }


async def verify_2fa(
    session_token: str,
    code: str | None,
    backup_code: str | None,
    session: AsyncSession,
) -> dict[str, object]:
    payload = _decode_2fa_session_token(
        session_token
    )
    user_id = int(str(payload["sub"]))

    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user or not user.is_active:
        raise EmailAuthError("User not found")
    if not user.totp_enabled:
        raise EmailAuthError("2FA is not enabled")
    if not user.totp_secret_encrypted:
        raise EmailAuthError("2FA not configured")

    secret = decrypt_secret(
        user.totp_secret_encrypted
    )

    if code:
        if not verify_totp(secret, code):
            raise EmailAuthError("Invalid TOTP code")
    elif backup_code:
        if not _verify_backup_code(
            user, backup_code
        ):
            raise EmailAuthError(
                "Invalid backup code"
            )
    else:
        raise EmailAuthError(
            "Provide code or backup_code"
        )

    access_token = create_access_token(
        user.id, user.is_admin
    )
    return {
        "access_token": access_token,
        "user_id": user.id,
        "is_admin": user.is_admin,
    }


def _verify_backup_code(
    user: User, code: str
) -> bool:
    if not user.backup_codes_hash:
        return False
    code_hash = hash_backup_code(code)
    stored: list[str] = json.loads(
        user.backup_codes_hash
    )
    if code_hash in stored:
        stored.remove(code_hash)
        user.backup_codes_hash = json.dumps(stored)
        return True
    return False


async def setup_2fa(
    user: User,
) -> dict[str, object]:
    if user.totp_enabled:
        raise EmailAuthError("2FA is already enabled")

    email = user.email or f"user_{user.id}"
    secret = generate_totp_secret()
    uri = get_otpauth_uri(secret, email)
    qr_b64 = generate_qr_base64(uri)
    backup_codes = generate_backup_codes()

    user.totp_secret_encrypted = encrypt_secret(
        secret
    )
    user.backup_codes_hash = json.dumps(
        [hash_backup_code(c) for c in backup_codes]
    )

    return {
        "otpauth_uri": uri,
        "qr_code_base64": qr_b64,
        "backup_codes": backup_codes,
        "secret": secret,
    }


async def confirm_2fa(
    user: User, code: str
) -> None:
    if user.totp_enabled:
        raise EmailAuthError("2FA is already enabled")
    if not user.totp_secret_encrypted:
        raise EmailAuthError(
            "Call setup first"
        )

    secret = decrypt_secret(
        user.totp_secret_encrypted
    )
    if not verify_totp(secret, code):
        raise EmailAuthError("Invalid TOTP code")

    user.totp_enabled = True


async def disable_2fa(
    user: User, code: str
) -> None:
    if not user.totp_enabled:
        raise EmailAuthError("2FA is not enabled")
    if not user.totp_secret_encrypted:
        raise EmailAuthError("2FA not configured")

    secret = decrypt_secret(
        user.totp_secret_encrypted
    )
    if not verify_totp(secret, code):
        raise EmailAuthError("Invalid TOTP code")

    user.totp_enabled = False
    user.totp_secret_encrypted = None
    user.backup_codes_hash = None


async def send_2fa_fallback(
    session_token: str,
    session: AsyncSession,
) -> None:
    payload = _decode_2fa_session_token(
        session_token
    )
    user_id = int(str(payload["sub"]))

    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user or not user.email:
        raise EmailAuthError(
            "User not found or no email"
        )

    redis = await _get_redis()

    cooldown_key = (
        f"{FALLBACK_PREFIX}"
        f"cooldown:{user.id}"
    )
    if await redis.exists(cooldown_key):
        await redis.aclose()
        raise EmailAuthError(
            "Too many failed attempts. "
            "Try again later"
        )

    rate_key = (
        f"{FALLBACK_PREFIX}{user.id}"
    )
    if await redis.exists(rate_key):
        await redis.aclose()
        raise EmailAuthError(
            "Please wait before requesting "
            "another code"
        )

    code = f"{secrets.randbelow(10**6):06d}"
    await redis.setex(
        f"{FALLBACK_PREFIX}code:{user.id}",
        FALLBACK_CODE_TTL,
        code,
    )
    await redis.setex(
        rate_key, FALLBACK_RATE_TTL, "1"
    )
    await redis.delete(
        f"{FALLBACK_PREFIX}"
        f"attempts:{user.id}"
    )
    await redis.aclose()

    await send_totp_fallback_code(user.email, code)


async def verify_2fa_email_code(
    session_token: str,
    code: str,
    session: AsyncSession,
) -> dict[str, object]:
    payload = _decode_2fa_session_token(
        session_token
    )
    user_id = int(str(payload["sub"]))

    redis = await _get_redis()

    cooldown_key = (
        f"{FALLBACK_PREFIX}"
        f"cooldown:{user_id}"
    )
    if await redis.exists(cooldown_key):
        await redis.aclose()
        raise EmailAuthError(
            "Too many failed attempts. "
            "Try again later"
        )

    code_key = (
        f"{FALLBACK_PREFIX}code:{user_id}"
    )
    stored = await redis.get(code_key)
    if not stored:
        await redis.aclose()
        raise EmailAuthError(
            "Code expired or not found"
        )

    if stored.decode() != code:
        attempts_key = (
            f"{FALLBACK_PREFIX}"
            f"attempts:{user_id}"
        )
        attempts = await redis.incr(attempts_key)
        await redis.expire(
            attempts_key, FALLBACK_CODE_TTL
        )

        if should_burn_code(attempts):
            await redis.delete(code_key)
            await redis.delete(attempts_key)
            burned_key = (
                f"{FALLBACK_PREFIX}"
                f"burned:{user_id}"
            )
            burned = await redis.incr(burned_key)
            await redis.expire(
                burned_key, FALLBACK_COOLDOWN_TTL
            )
            if should_cooldown_account(burned):
                await redis.setex(
                    cooldown_key,
                    FALLBACK_COOLDOWN_TTL,
                    "1",
                )
                logger.warning(
                    "2fa_fallback_account_cooldown",
                    user_id=user_id,
                )
            logger.warning(
                "2fa_fallback_code_burned",
                user_id=user_id,
            )
            await redis.aclose()
            raise EmailAuthError(
                "Code invalidated due to "
                "too many attempts"
            )

        await redis.aclose()
        raise EmailAuthError("Invalid code")

    await redis.delete(code_key)
    await redis.delete(
        f"{FALLBACK_PREFIX}"
        f"attempts:{user_id}"
    )
    await redis.aclose()

    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user or not user.is_active:
        raise EmailAuthError("User not found")

    access_token = create_access_token(
        user.id, user.is_admin
    )
    return {
        "access_token": access_token,
        "user_id": user.id,
        "is_admin": user.is_admin,
    }
