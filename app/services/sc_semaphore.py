"""Process-wide Redis semaphore around outbound SoundCloud calls.

The SoundCloud public API is shared by every backend worker that
ever needs to search for a track or resolve a streaming URL.
Without a global limit, a parallel-import storm can hammer the
upstream and burn the ``SC_CLIENT_ID`` quota fast.

This module implements a Redis-backed counting semaphore on a
sorted set: each acquired slot adds an entry whose score is its
expiry timestamp, the acquire path first removes expired entries
and then refuses if the live count is at the cap. Slots are
auto-released on ``slot_ttl_seconds`` so a crashed worker doesn't
permanently block the others.

Additional helpers
------------------
``get_active_slot_count()``  — instantaneous occupancy (no side effects).
``get_slot_stats()``         — occupancy + hourly timeout counter for
                               observability endpoints.
``SoundCloudSlotSaturated``  — raised by callers that want fast-fail
                               behaviour when the pool is near full (used
                               by low-priority background sweeps).
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog

from app.config import settings
from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SEMAPHORE_KEY = "sc:semaphore:active"
_DEFAULT_SLOT_TTL_SECONDS = 30.0
_RETRY_MIN_SECONDS = 0.5
_RETRY_MAX_SECONDS = 1.5
_TIMEOUT_COUNTER_PREFIX = "sc:slot:timeout:"
_TIMEOUT_COUNTER_TTL_SECONDS = 7200

_ACQUIRE_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[2]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
return 1
"""

_COUNT_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
return redis.call('ZCARD', KEYS[1])
"""


class SoundCloudSemaphoreTimeout(Exception):
    """Raised when a slot cannot be acquired within ``timeout``."""


class SoundCloudSlotSaturated(Exception):
    """Raised by low-priority callers when the pool is near capacity.

    Background sweeps catch this and skip the current cycle rather
    than queueing behind live user traffic.
    """


async def _try_acquire(
    token: str,
    *,
    max_active: int,
    slot_ttl_seconds: float,
) -> bool:
    redis = get_redis_client()
    now = time.time()
    expires_at = now + slot_ttl_seconds
    result = await redis.eval(
        _ACQUIRE_LUA,
        1,
        _SEMAPHORE_KEY,
        str(now),
        str(max_active),
        str(expires_at),
        token,
    )
    return bool(int(result))


async def _release(token: str) -> None:
    try:
        redis = get_redis_client()
        await redis.zrem(_SEMAPHORE_KEY, token)
    except Exception:
        logger.debug("sc_semaphore_release_failed", token=token)


async def _increment_timeout_counter() -> None:
    try:
        redis = get_redis_client()
        hour_key = _TIMEOUT_COUNTER_PREFIX + datetime.now(
            timezone.utc
        ).strftime("%Y%m%d%H")
        await redis.incr(hour_key)
        await redis.expire(hour_key, _TIMEOUT_COUNTER_TTL_SECONDS)
    except Exception:
        pass


async def get_active_slot_count() -> int:
    """Return the number of currently live semaphore slots.

    Expired entries are pruned atomically before the count is read, so
    the result reflects real occupancy rather than stale entries from
    crashed workers.
    """
    try:
        redis = get_redis_client()
        result = await redis.eval(
            _COUNT_LUA,
            1,
            _SEMAPHORE_KEY,
            str(time.time()),
        )
        return int(result)
    except Exception:
        return 0


async def get_slot_stats() -> dict:
    """Return semaphore observability snapshot.

    Shape::

        {
            "active": int,          # live slots right now
            "max_active": int,      # configured cap
            "saturated": bool,      # active >= max_active
            "timeouts_last_hour": int,
        }
    """
    max_active = max(1, int(settings.soundcloud_global_concurrency))
    active = await get_active_slot_count()
    timeouts = 0
    try:
        redis = get_redis_client()
        hour_key = _TIMEOUT_COUNTER_PREFIX + datetime.now(
            timezone.utc
        ).strftime("%Y%m%d%H")
        raw = await redis.get(hour_key)
        if raw is not None:
            timeouts = int(raw)
    except Exception:
        pass
    return {
        "active": active,
        "max_active": max_active,
        "saturated": active >= max_active,
        "timeouts_last_hour": timeouts,
    }


@asynccontextmanager
async def soundcloud_slot(
    *,
    timeout_seconds: float = 30.0,
    slot_ttl_seconds: float = _DEFAULT_SLOT_TTL_SECONDS,
) -> AsyncIterator[None]:
    """Acquire a SoundCloud-call slot for the duration of the
    ``async with`` block.

    Raises :class:`SoundCloudSemaphoreTimeout` when no slot becomes
    available within ``timeout_seconds``. Always releases the slot
    on exit (even on exception).
    """
    max_active = max(1, int(settings.soundcloud_global_concurrency))
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    attempt = 0
    while True:
        if await _try_acquire(
            token,
            max_active=max_active,
            slot_ttl_seconds=slot_ttl_seconds,
        ):
            break
        attempt += 1
        if time.monotonic() >= deadline:
            await _increment_timeout_counter()
            logger.warning(
                "sc_semaphore_timeout",
                attempts=attempt,
                max_active=max_active,
            )
            raise SoundCloudSemaphoreTimeout(
                f"could not acquire SoundCloud slot within "
                f"{timeout_seconds}s "
                f"(max_active={max_active})"
            )
        if attempt == 1:
            current = await get_active_slot_count()
            if current >= max_active - 1:
                logger.warning(
                    "sc_semaphore_near_saturation",
                    active=current,
                    max_active=max_active,
                )
        await asyncio.sleep(
            random.uniform(_RETRY_MIN_SECONDS, _RETRY_MAX_SECONDS)
        )

    try:
        yield
    finally:
        await _release(token)


__all__ = [
    "SoundCloudSemaphoreTimeout",
    "SoundCloudSlotSaturated",
    "get_active_slot_count",
    "get_slot_stats",
    "soundcloud_slot",
]
