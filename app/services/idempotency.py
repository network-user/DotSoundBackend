"""Redis-backed idempotency guard for background-task enqueue.

Use ``acquire_idempotency_slot()`` before inserting a BackgroundJob
row when callers must not enqueue the same logical work twice
within ``ttl_seconds`` (e.g. an artist enrichment kicked from
multiple endpoints near-simultaneously).
"""

from __future__ import annotations

import structlog

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

IDEMPOTENCY_KEY_PREFIX = "bgjob:idemp:"


async def acquire_idempotency_slot(
    key: str, *, ttl_seconds: int = 600
) -> bool:
    """Try to claim an idempotency slot. ``True`` on first claim.

    Returns ``False`` if the same key was claimed within the TTL —
    caller should skip enqueueing and treat as a duplicate.
    """
    redis = get_redis_client()
    try:
        ok = await redis.set(
            f"{IDEMPOTENCY_KEY_PREFIX}{key}",
            "1",
            ex=ttl_seconds,
            nx=True,
        )
    except Exception:
        logger.exception("idempotency_slot_failed", key=key)
        # Fail-open: if Redis is down we'd rather double-enqueue
        # than block all background work.
        return True
    return bool(ok)


async def release_idempotency_slot(key: str) -> None:
    redis = get_redis_client()
    try:
        await redis.delete(f"{IDEMPOTENCY_KEY_PREFIX}{key}")
    except Exception:
        logger.debug("idempotency_release_failed", key=key)
