"""Short-circuit cache for SoundCloud tracks known to be unavailable.

SoundCloud returns 404 / 410 on tracks that have been deleted,
made private, or geo-locked at the catalog level. Without a
cache, the catalog-sync sweep keeps re-scheduling them every cron
iteration -- each attempt costs one SC API call, eats one Tor
circuit slot, and ends in a dead-letter alert.

Marking such tracks in a short-TTL Redis key lets every subsequent
``fetch_track_by_ref`` short-circuit immediately. The TTL (defined
in PrivateCore policy) is intentionally finite so that genuinely
restored tracks rejoin the sync after the window elapses.
"""

from __future__ import annotations

import structlog
from dotsound_private_core.services.sc_anti_block_policy import (
    SC_DEAD_TRACK_COOLDOWN_SECONDS,
)

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_KEY_PREFIX = "sc:track_dead:"


def _key(track_ref: str | int) -> str:
    return f"{_KEY_PREFIX}{track_ref}"


async def is_dead(track_ref: str | int) -> bool:
    try:
        redis = get_redis_client()
        return bool(await redis.exists(_key(track_ref)))
    except Exception as exc:
        logger.debug("sc_dead_cache_check_failed", error=str(exc)[:200])
        return False


async def mark_dead(
    track_ref: str | int,
    *,
    reason: str = "",
    ttl_seconds: int | None = None,
) -> None:
    ttl = (
        ttl_seconds
        if ttl_seconds is not None
        else SC_DEAD_TRACK_COOLDOWN_SECONDS
    )
    try:
        redis = get_redis_client()
        await redis.set(
            _key(track_ref),
            (reason or "dead")[:120],
            ex=int(ttl),
        )
        logger.info(
            "sc_dead_track_cached",
            track_ref=str(track_ref),
            ttl_seconds=int(ttl),
            reason=(reason or "")[:80],
        )
    except Exception as exc:
        logger.warning(
            "sc_dead_track_cache_write_failed",
            track_ref=str(track_ref),
            error=str(exc)[:200],
        )


async def clear(track_ref: str | int) -> None:
    """Forget the dead-marker so the next call re-probes upstream."""
    try:
        redis = get_redis_client()
        await redis.delete(_key(track_ref))
    except Exception:
        pass


async def count_dead() -> int:
    """Cheap-ish count for admin dashboards. Uses SCAN to avoid
    blocking Redis on a large keyspace."""
    try:
        redis = get_redis_client()
        cursor = 0
        total = 0
        match = f"{_KEY_PREFIX}*"
        while True:
            cursor, batch = await redis.scan(
                cursor=cursor, match=match, count=500
            )
            total += len(batch)
            if cursor == 0:
                break
        return total
    except Exception:
        return -1


__all__ = [
    "clear",
    "count_dead",
    "is_dead",
    "mark_dead",
]
