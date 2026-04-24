"""Lightweight check of Telegram music profile (via DotSoundBot), for onboarding."""

from __future__ import annotations

import json
import time

import httpx
import structlog
from dotsound_private_core.services import (
    build_internal_headers,
    profile_audios_url,
)

from app.config import settings
from app.core.redis import get_redis_client
from app.models.user import User

logger = structlog.get_logger(__name__)

_BOT_TIMEOUT = 15.0
_CACHE_TTL_SEC = 120
_CACHE_KEY = "onboarding:tg_profile_audios:{user_id}"


class TelegramProfilePreflight:
    """Result of checking whether the user's TG profile has importable music."""

    __slots__ = ("can_import_from_telegram", "has_telegram_profile_music")

    def __init__(
        self,
        *,
        can_import_from_telegram: bool,
        has_telegram_profile_music: bool | None,
    ) -> None:
        self.can_import_from_telegram = can_import_from_telegram
        self.has_telegram_profile_music = has_telegram_profile_music


async def preflight_telegram_profile_music(
    user: User,
) -> TelegramProfilePreflight:
    """Call bot audios list; return whether Telegram import CTA should show."""
    if user.telegram_id is None:
        return TelegramProfilePreflight(
            can_import_from_telegram=False,
            has_telegram_profile_music=None,
        )

    if not settings.bot_internal_url or not settings.bot_internal_secret:
        return TelegramProfilePreflight(
            can_import_from_telegram=False,
            has_telegram_profile_music=None,
        )

    redis = get_redis_client()
    cache_key = _CACHE_KEY.format(user_id=user.id)
    try:
        raw = await redis.get(cache_key)
        if raw is not None:
            data = json.loads(raw)
            n = int(data.get("n", 0))
            return TelegramProfilePreflight(
                can_import_from_telegram=n > 0,
                has_telegram_profile_music=n > 0,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("tg_preflight_cache_read_failed", error=str(exc))

    try:
        async with httpx.AsyncClient(timeout=_BOT_TIMEOUT) as client:
            resp = await client.get(
                profile_audios_url(
                    settings.bot_internal_url,
                    user.telegram_id,
                ),
                headers=build_internal_headers(
                    settings.bot_internal_secret
                ),
            )
    except Exception as exc:
        logger.warning("tg_preflight_http_error", error=str(exc))
        return TelegramProfilePreflight(
            can_import_from_telegram=False,
            has_telegram_profile_music=None,
        )

    if resp.status_code != 200:
        logger.warning(
            "tg_preflight_bad_status",
            status=resp.status_code,
        )
        return TelegramProfilePreflight(
            can_import_from_telegram=False,
            has_telegram_profile_music=None,
        )

    try:
        body = resp.json()
    except Exception as exc:
        logger.warning("tg_preflight_json_error", error=str(exc))
        return TelegramProfilePreflight(
            can_import_from_telegram=False,
            has_telegram_profile_music=None,
        )

    audios = body.get("audios") or []
    n = len(audios) if isinstance(audios, list) else 0

    try:
        await redis.setex(
            cache_key,
            _CACHE_TTL_SEC,
            json.dumps({"n": n, "t": int(time.time())}),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("tg_preflight_cache_write_failed", error=str(exc))

    return TelegramProfilePreflight(
        can_import_from_telegram=n > 0,
        has_telegram_profile_music=n > 0,
    )
