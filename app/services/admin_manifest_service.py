"""Admin manifest builder.

Serves as the source of truth for what an admin can see and do
in the UI. Non-admin users never reach this code — backend
returns 404 for them before any construction happens.

All strings shown to the user are resolved server-side so they
don't end up in the public JS bundle.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.models.admin_capability import AdminCapability
from app.models.user import User
from app.repositories.admin_capability import (
    AdminCapabilityRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_CAPS_CACHE_KEY = "admin:capabilities:{user_id}"
_CAPS_CACHE_TTL_SECONDS = 30

KNOWN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "users.manage",
        "users.grant_admin",
        "users.ban",
        "users.unban",
        "users.revoke_admin",
        "users.grant_capability",
        "users.revoke_capability",
        "users.force_logout",
        "users.message",
        "tracks.manage",
        "tracks.delete",
        "promotions.manage",
        "complaints.moderate",
        "artists.enrich",
        "audio_compute.manage",
        "audio_compute.view_audit",
        "audio_compute.rotate_secret",
        "lyrics.routing",
        "metrics.view",
        "recsys.genre_samples.manage",
        "settings.manage",
        "logs.view",
        "containers.view",
        "tasks.manage",
        "tasks.run",
        "security.view",
        "security.release_lockout",
        "feature_flags.manage",
        "backups.view",
        "backups.run",
        "audit.view",
        "audit.export",
        "recsys.manage",
        "antivirus.view",
    }
)


_LABELS_RU: dict[str, str] = {
    "menu.dashboard": "Дашборд",
    "menu.users": "Пользователи",
    "menu.tracks": "Треки",
    "menu.track_timecodes": "Таймкоды",
    "menu.albums": "Альбомы",
    "menu.playlists": "Плейлисты",
    "menu.promotions": "Продвижение",
    "menu.complaints": "Жалобы",
    "menu.artists": "Артисты",
    "menu.station_gap": "Пробелы станций",
    "menu.audio_compute": "Вычисления",
    "menu.tasks": "Задачи",
    "menu.schedules": "Расписания",
    "menu.logs": "Логи",
    "menu.metrics": "Метрики",
    "menu.containers": "Контейнеры",
    "menu.audit": "Аудит",
    "menu.security": "Безопасность",
    "menu.settings": "Настройки",
    "menu.recsys": "Рекомендации",
    "menu.antivirus": "Антивирус",
    "slot.tracks.hide": "Скрыть",
    "slot.tracks.delete": "Удалить",
    "slot.artists.enrich": "Обогатить",
    "slot.complaints.resolve": "Решить",
}
_LABELS_EN: dict[str, str] = {
    "menu.dashboard": "Dashboard",
    "menu.users": "Users",
    "menu.tracks": "Tracks",
    "menu.track_timecodes": "Timecodes",
    "menu.albums": "Albums",
    "menu.playlists": "Playlists",
    "menu.promotions": "Promotions",
    "menu.complaints": "Complaints",
    "menu.artists": "Artists",
    "menu.station_gap": "Station gaps",
    "menu.audio_compute": "Compute",
    "menu.tasks": "Tasks",
    "menu.schedules": "Schedules",
    "menu.logs": "Logs",
    "menu.metrics": "Metrics",
    "menu.containers": "Containers",
    "menu.audit": "Audit",
    "menu.security": "Security",
    "menu.settings": "Settings",
    "menu.recsys": "Recsys",
    "menu.antivirus": "Antivirus",
    "slot.tracks.hide": "Hide",
    "slot.tracks.delete": "Delete",
    "slot.artists.enrich": "Enrich",
    "slot.complaints.resolve": "Resolve",
}


def _labels(locale: str) -> dict[str, str]:
    if locale.lower().startswith("ru"):
        return _LABELS_RU
    return _LABELS_EN


async def ensure_admin_capabilities_for_initialized(
    session: AsyncSession,
    user: User,
) -> None:
    if not user.is_admin or not user.admin_init:
        return
    repo = AdminCapabilityRepository(session)
    await repo.grant_all_known_if_empty(
        user_id=user.id,
        capabilities=KNOWN_CAPABILITIES,
    )


async def _effective_capabilities(
    session: AsyncSession, user: User
) -> set[str]:
    if not user.is_admin:
        return set()
    redis = get_redis_client()
    cache_key = _CAPS_CACHE_KEY.format(user_id=user.id)
    try:
        cached = await redis.get(cache_key)
    except Exception:
        cached = None
    if cached:
        try:
            payload = json.loads(
                cached if isinstance(cached, str) else cached.decode()
            )
            if isinstance(payload, list):
                return {
                    cap for cap in payload if cap in KNOWN_CAPABILITIES
                }
        except (TypeError, ValueError):
            pass

    result = await session.execute(
        select(AdminCapability).where(AdminCapability.user_id == user.id)
    )
    rows = result.scalars().all()
    caps = {
        row.capability for row in rows if row.capability in KNOWN_CAPABILITIES
    }
    try:
        await redis.set(
            cache_key,
            json.dumps(sorted(caps)),
            ex=_CAPS_CACHE_TTL_SECONDS,
        )
    except Exception:
        logger.debug("admin_capabilities_cache_write_failed")
    return caps


async def invalidate_admin_capabilities_cache(user_id: int) -> None:
    """Drop the per-user capabilities cache.

    Call after granting/revoking a capability so the change is
    visible before the natural TTL expires.
    """
    redis = get_redis_client()
    try:
        await redis.delete(_CAPS_CACHE_KEY.format(user_id=user_id))
    except Exception:
        logger.debug("admin_capabilities_cache_invalidate_failed")


def _filter_menu(caps: set[str], locale: str) -> list[dict]:
    labels = _labels(locale)
    base = settings.admin_panel_route_prefix
    raw: list[dict] = [
        {
            "id": "dashboard",
            "label": labels["menu.dashboard"],
            "route": base,
            "capability": None,
            "icon": "home",
        },
        {
            "id": "users",
            "label": labels["menu.users"],
            "route": f"{base}/users",
            "capability": "users.manage",
            "icon": "user",
        },
        {
            "id": "tracks",
            "label": labels["menu.tracks"],
            "route": f"{base}/tracks",
            "capability": "tracks.manage",
            "icon": "music",
        },
        {
            "id": "track-timecodes",
            "label": labels["menu.track_timecodes"],
            "route": f"{base}/tracks/timecode-sync",
            "capability": "tracks.manage",
            "icon": "clock",
        },
        {
            "id": "albums",
            "label": labels["menu.albums"],
            "route": f"{base}/albums",
            "capability": "tracks.manage",
            "icon": "list",
        },
        {
            "id": "playlists",
            "label": labels["menu.playlists"],
            "route": f"{base}/playlists",
            "capability": "tracks.manage",
            "icon": "edit",
        },
        {
            "id": "promotions",
            "label": labels["menu.promotions"],
            "route": f"{base}/promotions",
            "capability": "tracks.manage",
            "icon": "sparkle",
        },
        {
            "id": "complaints",
            "label": labels["menu.complaints"],
            "route": f"{base}/complaints",
            "capability": "complaints.moderate",
            "icon": "flag",
        },
        {
            "id": "artists",
            "label": labels["menu.artists"],
            "route": f"{base}/artists",
            "capability": "artists.enrich",
            "icon": "sparkle",
        },
        {
            "id": "station-gap",
            "label": labels["menu.station_gap"],
            "route": f"{base}/artists/station-gap",
            "capability": "artists.enrich",
            "icon": "radio",
        },
        {
            "id": "audio_compute",
            "label": labels["menu.audio_compute"],
            "route": f"{base}/audio-compute",
            "capability": "audio_compute.manage",
            "icon": "brain",
        },
        {
            "id": "tasks",
            "label": labels["menu.tasks"],
            "route": f"{base}/tasks",
            "capability": "tasks.manage",
            "icon": "queue",
        },
        {
            "id": "schedules",
            "label": labels["menu.schedules"],
            "route": f"{base}/schedules",
            "capability": "tasks.manage",
            "icon": "clock",
        },
        {
            "id": "logs",
            "label": labels["menu.logs"],
            "route": f"{base}/logs",
            "capability": "logs.view",
            "icon": "list",
        },
        {
            "id": "metrics",
            "label": labels["menu.metrics"],
            "route": f"{base}/metrics",
            "capability": "metrics.view",
            "icon": "trending-up",
        },
        {
            "id": "network",
            "label": "Network",
            "route": f"{base}/network",
            "capability": "metrics.view",
            "icon": "globe",
        },
        {
            "id": "containers",
            "label": labels["menu.containers"],
            "route": f"{base}/containers",
            "capability": "containers.view",
            "icon": "box",
        },
        {
            "id": "audit",
            "label": labels["menu.audit"],
            "route": f"{base}/audit",
            "capability": "audit.view",
            "icon": "eye",
        },
        {
            "id": "security",
            "label": labels["menu.security"],
            "route": f"{base}/security",
            "capability": "security.view",
            "icon": "shield",
        },
        {
            "id": "settings",
            "label": labels["menu.settings"],
            "route": f"{base}/settings",
            "capability": "settings.manage",
            "icon": "settings",
        },
        {
            "id": "recsys",
            "label": labels["menu.recsys"],
            "route": f"{base}/recsys",
            "capability": "recsys.manage",
            "icon": "sparkle",
        },
        {
            "id": "antivirus",
            "label": labels["menu.antivirus"],
            "route": f"{base}/antivirus",
            "capability": "antivirus.view",
            "icon": "shield",
        },
    ]
    return [
        m for m in raw if m["capability"] is None or m["capability"] in caps
    ]


def _filter_slots(caps: set[str], locale: str) -> dict[str, list[dict]]:
    labels = _labels(locale)
    raw: dict[str, list[dict]] = {
        "track.card": [
            {
                "id": "hide",
                "label": labels["slot.tracks.hide"],
                "capability": "tracks.manage",
                "icon": "eye",
                "action": "tracks.hide",
            },
            {
                "id": "delete",
                "label": labels["slot.tracks.delete"],
                "capability": "tracks.delete",
                "icon": "trash",
                "action": "tracks.delete",
                "confirm": True,
            },
        ],
        "artist.page": [
            {
                "id": "enrich",
                "label": labels["slot.artists.enrich"],
                "capability": "artists.enrich",
                "icon": "sparkle",
                "action": "artists.enrich",
            },
        ],
        "complaint.row": [
            {
                "id": "resolve",
                "label": labels["slot.complaints.resolve"],
                "capability": "complaints.moderate",
                "icon": "check",
                "action": "complaints.resolve",
            },
        ],
    }
    filtered: dict[str, list[dict]] = {}
    for ctx, items in raw.items():
        allowed = [i for i in items if i["capability"] in caps]
        if allowed:
            filtered[ctx] = allowed
    return filtered


def sign_bundle_token(
    user_id: int, ttl_s: int | None = None
) -> tuple[str, int]:
    from dotsound_private_core.services.admin_security_policy import (
        ADMIN_BUNDLE_TTL_SECONDS,
    )

    effective_ttl = ttl_s if ttl_s is not None else ADMIN_BUNDLE_TTL_SECONDS
    exp = int(time.time()) + int(effective_ttl)
    raw = f"admin:{user_id}:{exp}"
    sig = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{exp}.{sig}", exp


def verify_bundle_token(token: str, user_id: int) -> bool:
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except (ValueError, AttributeError):
        return False
    if exp < int(time.time()):
        return False
    raw = f"admin:{user_id}:{exp}"
    expected = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


async def build_manifest(
    session: AsyncSession,
    user: User,
    *,
    locale: str | None = None,
) -> dict:
    loc = (locale or getattr(user, "locale", None) or "ru").strip()
    await ensure_admin_capabilities_for_initialized(session, user)
    caps = await _effective_capabilities(session, user)

    menu = _filter_menu(caps, loc)
    slots = _filter_slots(caps, loc)

    token, exp = sign_bundle_token(user.id)
    bundle_url = (
        f"/mini_app/assets/secure/admin-bundle.js" f"?t={token}&u={user.id}"
    )
    issued_at = int(time.time())

    return {
        "capabilities": sorted(caps),
        "menu": menu,
        "slots": slots,
        "adminBundleUrl": bundle_url,
        "issuedAt": issued_at,
        "expiresIn": max(60, exp - issued_at),
        "locale": loc,
    }


__all__ = [
    "KNOWN_CAPABILITIES",
    "build_manifest",
    "ensure_admin_capabilities_for_initialized",
    "invalidate_admin_capabilities_cache",
    "sign_bundle_token",
    "verify_bundle_token",
]
