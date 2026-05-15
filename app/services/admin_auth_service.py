from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any

import structlog
from dotsound_private_core.services.admin_security_policy import (
    ADMIN_BACKUP_CODES_COUNT,
    ADMIN_INIT_TTL_SECONDS,
    ADMIN_LOCKOUT_TTL_SECONDS,
    ADMIN_LOGIN_ATTEMPT_WINDOW_SECONDS,
    ADMIN_REFRESH_TTL_SECONDS,
    ADMIN_SESSION_TTL_SECONDS,
    ADMIN_STEP_UP_TTL_SECONDS,
    is_device_trust_expired,
    should_lockout_admin,
)
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthError,
    create_admin_token,
    decode_admin_token,
)
from app.core.redis import get_redis_client
from app.core.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_totp_secret,
    get_otpauth_uri,
    hash_backup_code,
    verify_totp,
)
from app.models.admin_device import AdminDevice
from app.models.admin_session import AdminSession
from app.models.user import User
from app.repositories.admin_device import (
    AdminDeviceRepository,
)
from app.repositories.admin_login_attempt import (
    AdminLoginAttemptRepository,
)
from app.repositories.admin_session import (
    AdminSessionRepository,
)
from app.services.admin_manifest_service import (
    ensure_admin_capabilities_for_initialized,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

INIT_REDIS_PREFIX = "admin:init:"
STEP_UP_REDIS_PREFIX = "admin:stepup:"
LOCKOUT_REDIS_PREFIX = "admin:lockout:"


class AdminAuthError(Exception):
    pass


def _normalize_fingerprint(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        raise AdminAuthError("device fingerprint required")
    if len(cleaned) > 256:
        raise AdminAuthError("fingerprint too long")
    return cleaned


def _new_jti() -> str:
    return secrets.token_urlsafe(24)


async def is_locked_out(user_id: int) -> bool:
    redis = get_redis_client()
    try:
        raw = await redis.get(f"{LOCKOUT_REDIS_PREFIX}{user_id}")
    except RedisError as exc:
        logger.warning(
            "admin_lockout_check_cache_unavailable",
            user_id=user_id,
            error=str(exc),
        )
        return False
    return bool(raw)


async def _set_lockout(user_id: int) -> None:
    redis = get_redis_client()
    try:
        await redis.setex(
            f"{LOCKOUT_REDIS_PREFIX}{user_id}",
            ADMIN_LOCKOUT_TTL_SECONDS,
            "1",
        )
    except RedisError as exc:
        logger.warning(
            "admin_lockout_set_cache_unavailable",
            user_id=user_id,
            error=str(exc),
        )


async def release_lockout(user_id: int) -> bool:
    redis = get_redis_client()
    try:
        return bool(
            await redis.delete(f"{LOCKOUT_REDIS_PREFIX}{user_id}")
        )
    except RedisError as exc:
        logger.warning(
            "admin_lockout_release_cache_unavailable",
            user_id=user_id,
            error=str(exc),
        )
        return False


async def start_admin_init(
    user: User,
) -> dict[str, object]:
    if not user.is_admin:
        raise AdminAuthError("user is not admin")
    if user.admin_init and user.admin_totp_enabled:
        raise AdminAuthError("admin already initialized")

    secret = generate_totp_secret()
    email_or_id = user.email or f"admin_{user.id}@dotsound.local"
    uri = get_otpauth_uri(secret, email_or_id)

    redis = get_redis_client()
    await redis.setex(
        f"{INIT_REDIS_PREFIX}{user.id}",
        ADMIN_INIT_TTL_SECONDS,
        secret,
    )

    return {
        "secret_b32": secret,
        "otpauth_uri": uri,
        "ttl_seconds": ADMIN_INIT_TTL_SECONDS,
    }


async def confirm_admin_init(
    *,
    user: User,
    code: str,
    fingerprint: str,
    label: str | None,
    ip: str | None,
    ua: str | None,
    session: AsyncSession,
) -> dict[str, object]:
    if not user.is_admin:
        raise AdminAuthError("user is not admin")
    if user.admin_init and user.admin_totp_enabled:
        raise AdminAuthError("admin already initialized")
    fp = _normalize_fingerprint(fingerprint)

    redis = get_redis_client()
    raw = await redis.get(f"{INIT_REDIS_PREFIX}{user.id}")
    if not raw:
        raise AdminAuthError("init session expired")
    secret = raw.decode() if isinstance(raw, bytes) else raw

    if not verify_totp(secret, code):
        raise AdminAuthError("invalid TOTP code")

    backup_codes = generate_backup_codes(ADMIN_BACKUP_CODES_COUNT)
    user.admin_totp_secret_encrypted = encrypt_secret(secret)
    user.admin_totp_enabled = True
    user.admin_init = True
    user.admin_backup_codes_hash = json.dumps(
        [hash_backup_code(c) for c in backup_codes]
    )
    await session.flush()
    await ensure_admin_capabilities_for_initialized(session, user)

    devices = AdminDeviceRepository(session)
    existing = await devices.get_by_fingerprint(user.id, fp)
    device = existing or await devices.create_pending(
        user_id=user.id,
        fingerprint_hash=fp,
        label=label,
        ip=ip,
        ua=ua,
    )
    await devices.trust(device)

    await redis.delete(f"{INIT_REDIS_PREFIX}{user.id}")

    issued = await issue_admin_session(
        user=user,
        device=device,
        ip=ip,
        ua=ua,
        session=session,
    )

    return {
        "backup_codes": backup_codes,
        "device_id": device.id,
        "session": issued,
    }


async def verify_admin_login(
    *,
    user: User,
    code: str,
    fingerprint: str,
    ip: str | None,
    ua: str | None,
    session: AsyncSession,
) -> dict[str, object]:
    if not user.is_admin:
        raise AdminAuthError("user is not admin")
    if (
        not user.admin_init
        or not user.admin_totp_enabled
        or not user.admin_totp_secret_encrypted
    ):
        raise AdminAuthError("admin not initialized")

    if await is_locked_out(user.id):
        raise AdminAuthError("account locked out")

    attempts = AdminLoginAttemptRepository(session)
    fp = _normalize_fingerprint(fingerprint)

    secret = decrypt_secret(user.admin_totp_secret_encrypted)
    if not verify_totp(secret, code):
        await attempts.record(
            user_id=user.id,
            ip=ip,
            ua=ua,
            success=False,
            reason="bad_code",
        )
        failures = await attempts.count_failures_in_window(
            user_id=user.id,
            window_seconds=(ADMIN_LOGIN_ATTEMPT_WINDOW_SECONDS),
        )
        if should_lockout_admin(failures):
            await _set_lockout(user.id)
            logger.warning(
                "admin_lockout_triggered",
                user_id=user.id,
                failures=failures,
            )
            raise AdminAuthError("account locked out")
        raise AdminAuthError("invalid TOTP code")

    devices = AdminDeviceRepository(session)
    device = await devices.get_by_fingerprint(user.id, fp)
    if device is None or device.revoked_at is not None:
        device = await devices.create_pending(
            user_id=user.id,
            fingerprint_hash=fp,
            label=None,
            ip=ip,
            ua=ua,
        )
        await attempts.record(
            user_id=user.id,
            ip=ip,
            ua=ua,
            success=True,
            reason="pending_device",
        )
        return {
            "requires_device_approval": True,
            "device_id": device.id,
        }

    if device.trusted_at is None or is_device_trust_expired(
        device.last_seen_at
    ):
        await attempts.record(
            user_id=user.id,
            ip=ip,
            ua=ua,
            success=True,
            reason="device_reapproval",
        )
        return {
            "requires_device_approval": True,
            "device_id": device.id,
        }

    await devices.touch(device, ip=ip)
    await attempts.record(
        user_id=user.id,
        ip=ip,
        ua=ua,
        success=True,
    )

    issued = await issue_admin_session(
        user=user,
        device=device,
        ip=ip,
        ua=ua,
        session=session,
    )
    return {
        "requires_device_approval": False,
        "session": issued,
    }


async def issue_admin_session(
    *,
    user: User,
    device: AdminDevice,
    ip: str | None,
    ua: str | None,
    session: AsyncSession,
) -> dict[str, object]:
    sessions = AdminSessionRepository(session)
    jti = _new_jti()
    refresh_jti = _new_jti()
    row = await sessions.create(
        user_id=user.id,
        device_id=device.id,
        jti=jti,
        refresh_jti=refresh_jti,
        ip=ip,
        ua=ua,
        ttl_seconds=ADMIN_SESSION_TTL_SECONDS,
    )
    access_token = create_admin_token(
        user_id=user.id,
        jti=jti,
        device_id=device.id,
        ttl_seconds=ADMIN_SESSION_TTL_SECONDS,
    )
    refresh_token = create_admin_token(
        user_id=user.id,
        jti=refresh_jti,
        device_id=device.id,
        ttl_seconds=ADMIN_REFRESH_TTL_SECONDS,
        scope="admin_refresh",
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "jti": jti,
        "refresh_jti": refresh_jti,
        "expires_in": ADMIN_SESSION_TTL_SECONDS,
        "session_id": row.id,
    }


async def rotate_admin_refresh(
    *,
    refresh_token: str,
    ip: str | None,
    ua: str | None,
    session: AsyncSession,
) -> dict[str, object]:
    try:
        payload = decode_admin_token(refresh_token)
    except AuthError as exc:
        raise AdminAuthError(str(exc)) from exc

    if payload.get("scope") != "admin_refresh":
        raise AdminAuthError("invalid refresh scope")

    refresh_jti = str(payload.get("jti", ""))
    if not refresh_jti:
        raise AdminAuthError("refresh missing jti")

    sessions = AdminSessionRepository(session)
    row = await sessions.get_by_refresh_jti(refresh_jti)
    if row is None or row.revoked_at is not None:
        raise AdminAuthError("refresh invalidated")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise AdminAuthError("refresh invalidated")

    new_jti = _new_jti()
    new_refresh = _new_jti()
    row.jti = new_jti
    await sessions.rotate_refresh(row, new_refresh_jti=new_refresh)
    await sessions.touch(row, ip=ip, ua=ua)

    access_token = create_admin_token(
        user_id=row.user_id,
        jti=new_jti,
        device_id=row.device_id,
        ttl_seconds=ADMIN_SESSION_TTL_SECONDS,
    )
    new_refresh_token = create_admin_token(
        user_id=row.user_id,
        jti=new_refresh,
        device_id=row.device_id,
        ttl_seconds=ADMIN_REFRESH_TTL_SECONDS,
        scope="admin_refresh",
    )
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": ADMIN_SESSION_TTL_SECONDS,
    }


async def revoke_admin_session(*, jti: str, session: AsyncSession) -> bool:
    sessions = AdminSessionRepository(session)
    row = await sessions.get_by_jti(jti)
    if row is None or row.revoked_at is not None:
        return False
    await sessions.revoke(row)
    return True


async def verify_step_up(
    *,
    user: User,
    code: str,
    action: str,
    ttl_seconds: int = ADMIN_STEP_UP_TTL_SECONDS,
) -> bool:
    if not user.admin_totp_secret_encrypted:
        raise AdminAuthError("admin not initialized")
    secret = decrypt_secret(user.admin_totp_secret_encrypted)
    if not verify_totp(secret, code):
        return False
    redis = get_redis_client()
    await redis.setex(
        f"{STEP_UP_REDIS_PREFIX}{user.id}:{action}",
        ttl_seconds,
        "1",
    )
    return True


async def consume_step_up(*, user_id: int, action: str) -> bool:
    redis = get_redis_client()
    key = f"{STEP_UP_REDIS_PREFIX}{user_id}:{action}"
    try:
        getdel = getattr(redis, "getdel", None)
        if callable(getdel):
            raw = await getdel(key)
            return bool(raw)

        get_fn = getattr(redis, "get", None)
        delete_fn = getattr(redis, "delete", None)
        if callable(get_fn) and callable(delete_fn):
            raw = await get_fn(key)
            if raw:
                await delete_fn(key)
            return bool(raw)

        async with redis.pipeline(transaction=True) as pipe:
            pipe.get(key)
            pipe.delete(key)
            results = await pipe.execute()
        raw = results[0] if results else None
        return bool(raw)
    except RedisError as exc:
        logger.warning(
            "admin_step_up_cache_unavailable",
            user_id=user_id,
            action=action,
            error=str(exc),
        )
        return False


async def has_step_up(*, user_id: int, action: str) -> bool:
    return await consume_step_up(user_id=user_id, action=action)


def is_admin_session_valid(
    *,
    row: AdminSession | None,
) -> bool:
    if row is None:
        return False
    if row.revoked_at is not None:
        return False
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at >= datetime.now(UTC)


async def regenerate_backup_codes(
    *, user: User, session: AsyncSession
) -> list[str]:
    if not user.admin_init:
        raise AdminAuthError("admin not initialized")
    codes = generate_backup_codes(ADMIN_BACKUP_CODES_COUNT)
    user.admin_backup_codes_hash = json.dumps(
        [hash_backup_code(c) for c in codes]
    )
    await session.flush()
    return codes


async def consume_backup_code(
    *, user: User, code: str, session: AsyncSession
) -> bool:
    await session.refresh(user, with_for_update=True)
    if not user.admin_backup_codes_hash:
        return False
    raw = json.loads(user.admin_backup_codes_hash)
    if not isinstance(raw, list):
        return False
    target = hash_backup_code(code)
    if target not in raw:
        return False
    raw.remove(target)
    user.admin_backup_codes_hash = json.dumps(raw)
    await session.flush()
    return True


async def disable_admin_2fa(
    *, user: User, code: str, session: AsyncSession
) -> None:
    if not user.admin_totp_enabled or not user.admin_totp_secret_encrypted:
        raise AdminAuthError("admin 2FA is not enabled")
    secret = decrypt_secret(user.admin_totp_secret_encrypted)
    if not verify_totp(secret, code):
        raise AdminAuthError("invalid TOTP code")
    user.admin_totp_enabled = False
    user.admin_totp_secret_encrypted = None
    user.admin_backup_codes_hash = None
    user.admin_init = False
    await session.flush()


def metadata_summary(*, user: User) -> dict[str, Any]:
    return {
        "is_admin": bool(user.is_admin),
        "admin_init": bool(user.admin_init),
        "admin_totp_enabled": bool(user.admin_totp_enabled),
        "has_backup_codes": bool(user.admin_backup_codes_hash),
    }
