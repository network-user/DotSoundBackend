"""Process-wide Redis semaphores for outbound YouTube and Bandcamp calls.

Same pattern as :mod:`app.services.sc_semaphore` — one key per platform,
``youtube_concurrency`` / ``bandcamp_concurrency`` caps, optional slot TTL
for crash recovery on long calls (e.g. yt-dlp).
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog

from app.config import settings
from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_DEFAULT_RETRY_MIN_SECONDS = 0.5
_DEFAULT_RETRY_MAX_SECONDS = 1.5

_ACQUIRE_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[2]) then
  return 0
end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
return 1
"""


class OutboundSemaphoreTimeout(Exception):
    """No slot before ``timeout_seconds`` (YouTube or Bandcamp)."""


async def _try_acquire(
    redis_key: str,
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
        redis_key,
        str(now),
        str(max_active),
        str(expires_at),
        token,
    )
    return bool(int(result))


async def _release(redis_key: str, token: str) -> None:
    try:
        redis = get_redis_client()
        await redis.zrem(redis_key, token)
    except Exception:
        logger.debug(
            "outbound_semaphore_release_failed",
            key=redis_key,
            token=token,
        )


@asynccontextmanager
async def _acquired_outbound_slot(
    *,
    redis_key: str,
    max_active: int,
    timeout_seconds: float,
    log_event: str,
    slot_ttl_seconds: float,
) -> AsyncIterator[None]:
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    attempt = 0
    while True:
        if await _try_acquire(
            redis_key,
            token,
            max_active=max_active,
            slot_ttl_seconds=slot_ttl_seconds,
        ):
            break
        attempt += 1
        if time.monotonic() >= deadline:
            logger.warning(
                log_event,
                attempts=attempt,
                max_active=max_active,
                key=redis_key,
            )
            raise OutboundSemaphoreTimeout(
                f"could not acquire outbound slot within "
                f"{timeout_seconds}s (max_active={max_active}, key={redis_key})"
            )
        await asyncio.sleep(
            random.uniform(
                _DEFAULT_RETRY_MIN_SECONDS,
                _DEFAULT_RETRY_MAX_SECONDS,
            )
        )
    try:
        yield
    finally:
        await _release(redis_key, token)


@asynccontextmanager
async def youtube_slot(
    *,
    timeout_seconds: float | None = None,
    slot_ttl_seconds: float = 120.0,
) -> AsyncIterator[None]:
    t = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.youtube_slot_acquire_timeout_seconds
    )
    max_a = max(1, int(settings.youtube_concurrency))
    async with _acquired_outbound_slot(
        redis_key="yt:semaphore:active",
        max_active=max_a,
        timeout_seconds=t,
        log_event="yt_semaphore_timeout",
        slot_ttl_seconds=slot_ttl_seconds,
    ):
        yield


@asynccontextmanager
async def bandcamp_slot(
    *,
    timeout_seconds: float | None = None,
    slot_ttl_seconds: float = 60.0,
) -> AsyncIterator[None]:
    t = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.bandcamp_slot_acquire_timeout_seconds
    )
    max_a = max(1, int(settings.bandcamp_concurrency))
    async with _acquired_outbound_slot(
        redis_key="bc:semaphore:active",
        max_active=max_a,
        timeout_seconds=t,
        log_event="bc_semaphore_timeout",
        slot_ttl_seconds=slot_ttl_seconds,
    ):
        yield


__all__ = [
    "OutboundSemaphoreTimeout",
    "bandcamp_slot",
    "youtube_slot",
]
