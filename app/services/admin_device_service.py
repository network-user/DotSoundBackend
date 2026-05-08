from __future__ import annotations

import secrets

import httpx
import structlog
from dotsound_private_core.services.admin_security_policy import (
    ADMIN_DEVICE_APPROVAL_NOTIFY_COOLDOWN_SECONDS,
    ADMIN_DEVICE_PENDING_TTL_SECONDS,
)
from dotsound_private_core.services.internal_bridge import (
    build_internal_headers,
    send_auth_code_url,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.core.totp import (
    decrypt_secret,
    verify_totp,
)
from app.models.user import User
from app.repositories.admin_device import (
    AdminDeviceRepository,
)
from app.repositories.admin_session import (
    AdminSessionRepository,
)
from app.services.admin_auth_service import (
    AdminAuthError,
    issue_admin_session,
)
from app.services.email_sender import (
    send_totp_fallback_code,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DEVICE_PENDING_PREFIX = "admin:device_pending:"
DEVICE_NOTIFY_PREFIX = "admin:device_approval_notify:"


def _new_email_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _pending_key(user_id: int, device_id: int) -> str:
    return f"{DEVICE_PENDING_PREFIX}{user_id}:{device_id}"


def _notify_key(user_id: int, device_id: int) -> str:
    return f"{DEVICE_NOTIFY_PREFIX}{user_id}:{device_id}"


async def _send_device_code_via_telegram(
    telegram_id: int,
    code: str,
) -> None:
    if (
        not settings.bot_internal_url
        or not settings.bot_internal_secret.strip()
    ):
        logger.warning(
            "admin_device_code_telegram_unconfigured",
            telegram_id=telegram_id,
        )
        raise AdminAuthError(
            "telegram delivery unavailable for device approval"
        )
    url = send_auth_code_url(settings.bot_internal_url)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                headers=build_internal_headers(settings.bot_internal_secret),
                json={
                    "telegram_id": telegram_id,
                    "code": code,
                },
            )
    except Exception as exc:
        logger.exception(
            "admin_device_code_telegram_http_failed",
            telegram_id=telegram_id,
        )
        raise AdminAuthError(
            "could not send verification code via Telegram"
        ) from exc
    if resp.status_code >= 400:
        logger.warning(
            "admin_device_code_telegram_rejected",
            status_code=resp.status_code,
            body_preview=resp.text[:500],
        )
        raise AdminAuthError("could not send verification code via Telegram")


async def _deliver_device_approval_code(
    *,
    user: User,
    code: str,
) -> None:
    if user.email:
        await send_totp_fallback_code(user.email, code)
        return
    if user.telegram_id:
        await _send_device_code_via_telegram(
            int(user.telegram_id),
            code,
        )
        return
    raise AdminAuthError("no delivery channel: add email or link Telegram")


async def request_device_approval(
    *,
    user: User,
    device_id: int,
    session: AsyncSession,
    force_resend: bool = False,
) -> None:
    devices = AdminDeviceRepository(session)
    device = await devices.get_by_id(device_id)
    if (
        device is None
        or device.user_id != user.id
        or device.revoked_at is not None
    ):
        raise AdminAuthError("device not found")

    redis = get_redis_client()
    notify_key = _notify_key(user.id, device.id)
    if not force_resend:
        existing_notify = await redis.get(notify_key)
        if existing_notify:
            logger.info(
                "admin_device_approval_notify_skipped_cooldown",
                user_id=user.id,
                device_id=device.id,
            )
            return

    code = _new_email_code()
    await redis.setex(
        _pending_key(user.id, device.id),
        ADMIN_DEVICE_PENDING_TTL_SECONDS,
        code,
    )
    await redis.setex(
        notify_key,
        ADMIN_DEVICE_APPROVAL_NOTIFY_COOLDOWN_SECONDS,
        "1",
    )
    await _deliver_device_approval_code(user=user, code=code)
    logger.info(
        "admin_device_approval_requested",
        user_id=user.id,
        device_id=device.id,
        force_resend=force_resend,
    )


async def confirm_device_approval(
    *,
    user: User,
    device_id: int,
    email_code: str,
    totp_code: str,
    label: str | None,
    ip: str | None,
    ua: str | None,
    session: AsyncSession,
) -> dict[str, object]:
    if (
        not user.admin_init
        or not user.admin_totp_enabled
        or not user.admin_totp_secret_encrypted
    ):
        raise AdminAuthError("admin not initialized")

    devices = AdminDeviceRepository(session)
    device = await devices.get_by_id(device_id)
    if (
        device is None
        or device.user_id != user.id
        or device.revoked_at is not None
    ):
        raise AdminAuthError("device not found")

    redis = get_redis_client()
    key = _pending_key(user.id, device.id)
    raw = await redis.get(key)
    if not raw:
        raise AdminAuthError("approval expired or never requested")
    stored = raw.decode() if isinstance(raw, bytes) else raw
    if stored != email_code:
        raise AdminAuthError("invalid email code")

    secret = decrypt_secret(user.admin_totp_secret_encrypted)
    if not verify_totp(secret, totp_code):
        raise AdminAuthError("invalid TOTP code")

    if label is not None:
        device.label = label
    await devices.trust(device)
    await redis.delete(key)

    issued = await issue_admin_session(
        user=user,
        device=device,
        ip=ip,
        ua=ua,
        session=session,
    )
    return {
        "device_id": device.id,
        "session": issued,
    }


async def list_devices(
    *, user: User, session: AsyncSession
) -> list[dict[str, object]]:
    repo = AdminDeviceRepository(session)
    rows = await repo.list_active_for_user(user.id)
    return [
        {
            "id": row.id,
            "label": row.label,
            "fingerprint_hash_preview": (row.fingerprint_hash[:12]),
            "ip_first": row.ip_first,
            "ua_first": row.ua_first,
            "trusted_at": row.trusted_at,
            "last_seen_at": row.last_seen_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def revoke_device(
    *,
    user: User,
    device_id: int,
    session: AsyncSession,
) -> None:
    devices = AdminDeviceRepository(session)
    sessions = AdminSessionRepository(session)
    device = await devices.get_by_id(device_id)
    if device is None or device.user_id != user.id:
        raise AdminAuthError("device not found")
    await devices.revoke(device)
    await sessions.revoke_all_for_device(device.id)
    logger.info(
        "admin_device_revoked",
        user_id=user.id,
        device_id=device.id,
    )
