"""Routing policy for lyrics generation jobs.

Picks whether a job goes in-process (catalog-only / local CPU)
or is waiting for a remote worker to pull it. All labels are
opaque — algorithm and model selection live inside the private
core. The cascade *order* itself lives in PrivateCore
(`asr_policy.normalize_cascade`); this module wires it to the
DB-backed AppSettings store.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from dotsound_private_core.services.asr_policy import (
    DEFAULT_CASCADE,
    TIER_CATALOG_ONLY,
    TIER_REMOTE_WHISPER,
    TIER_SPEECHKIT_PAID,
    normalize_cascade,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.models.app_setting import AppSetting
from app.models.compute_worker import ComputeWorker

ROUTING_MODES = {
    "auto",
    "force_local_cpu",
    "force_remote_gpu",
    "disabled",
}

SETTING_ROUTING_MODE = "lyrics.routing_mode"
SETTING_HEARTBEAT_TIMEOUT = "lyrics.heartbeat_timeout_s"
SETTING_MAX_QUEUE_TIME = "lyrics.max_queue_time_s"
SETTING_CASCADE_ORDER = "lyrics.cascade_order"

_DEFAULT_ROUTING_MODE = "auto"
_DEFAULT_HEARTBEAT_TIMEOUT = 30
_DEFAULT_MAX_QUEUE_TIME = 600
_SETTINGS_CACHE_KEY = "app_settings:cache"
_SETTINGS_TTL = 30


async def _cached_setting(
    session: AsyncSession, key: str
) -> object | None:
    redis = get_redis_client()
    raw = await redis.hget(_SETTINGS_CACHE_KEY, key)
    if raw is not None:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            pass
    result = await session.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    entry = result.scalar_one_or_none()
    value = entry.value if entry else None
    await redis.hset(
        _SETTINGS_CACHE_KEY,
        key,
        json.dumps(value, ensure_ascii=False),
    )
    await redis.expire(_SETTINGS_CACHE_KEY, _SETTINGS_TTL)
    return value


async def get_routing_mode(session: AsyncSession) -> str:
    raw = await _cached_setting(session, SETTING_ROUTING_MODE)
    if isinstance(raw, dict):
        raw = raw.get("value")
    if raw in ROUTING_MODES:
        return raw  # type: ignore[return-value]
    return _DEFAULT_ROUTING_MODE


async def get_heartbeat_timeout(session: AsyncSession) -> int:
    raw = await _cached_setting(
        session, SETTING_HEARTBEAT_TIMEOUT
    )
    if isinstance(raw, dict):
        raw = raw.get("value")
    try:
        return int(raw) if raw is not None else _DEFAULT_HEARTBEAT_TIMEOUT
    except (TypeError, ValueError):
        return _DEFAULT_HEARTBEAT_TIMEOUT


async def invalidate_settings_cache() -> None:
    redis = get_redis_client()
    await redis.delete(_SETTINGS_CACHE_KEY)


async def any_worker_online(
    session: AsyncSession,
    *,
    profile: str,
) -> bool:
    heartbeat_timeout = await get_heartbeat_timeout(session)
    cutoff = datetime.now(UTC) - timedelta(
        seconds=heartbeat_timeout
    )
    result = await session.execute(
        select(ComputeWorker).where(
            ComputeWorker.profile == profile,
            ComputeWorker.active.is_(True),
            ComputeWorker.revoked_at.is_(None),
            ComputeWorker.last_seen_at.is_not(None),
            ComputeWorker.last_seen_at >= cutoff,
        )
    )
    return result.first() is not None


async def get_cascade_order(
    session: AsyncSession,
) -> tuple[str, ...]:
    """Read admin-configured cascade order, falling back to
    `DEFAULT_CASCADE` if the setting is missing or malformed.
    """
    raw = await _cached_setting(
        session, SETTING_CASCADE_ORDER
    )
    if isinstance(raw, dict):
        raw = raw.get("value")
    if not isinstance(raw, list):
        return DEFAULT_CASCADE
    return normalize_cascade(raw)


async def is_tier_available(
    session: AsyncSession,
    tier: str,
) -> bool:
    """True if ``tier`` can accept a job *right now*.

    - catalog_only: always available (Backend itself runs the task)
    - remote_whisper: at least one worker with profile=gpu_full
      and a fresh heartbeat
    - speechkit_paid: feature flag is on AND the monthly budget
      isn't exhausted (cheap pre-check; the per-job soft limit is
      re-evaluated by `lyrics_cascade._dispatch_to_tier`)
    """
    if tier == TIER_CATALOG_ONLY:
        return True
    if tier == TIER_REMOTE_WHISPER:
        return await any_worker_online(
            session, profile="gpu_full"
        )
    if tier == TIER_SPEECHKIT_PAID:
        if not settings.yandex_speechkit_enabled:
            return False
        budget = float(
            settings.yandex_speechkit_monthly_budget_rub
        )
        if budget <= 0:
            return False
        return True
    return False


async def select_profile(
    session: AsyncSession,
) -> str | None:
    """Legacy profile selector (kept for backward compatibility).

    Newer code should call `lyrics_cascade.start_cascade` which
    drives the full tier sequence; this helper is preserved for
    callers that still ask "which single profile should I queue?".
    """
    mode = await get_routing_mode(session)
    if mode == "disabled":
        return None
    if mode == "force_local_cpu":
        return "cpu_light"
    remote_available = await any_worker_online(
        session, profile="gpu_full"
    )
    if mode == "force_remote_gpu":
        return "gpu_full" if remote_available else None
    return (
        "gpu_full" if remote_available else "cpu_light"
    )
