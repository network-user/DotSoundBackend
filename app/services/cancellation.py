"""Generic Redis-backed cancellation signal for background jobs.

A long-running task should periodically check
``is_cancelled(job_id)`` and exit cleanly when it returns ``True``.
The lyrics worker has its own legacy ``CANCEL_KEY_PREFIX`` for the
progress channel; this module is the generic counterpart keyed by
``BackgroundJob.id``.
"""

from __future__ import annotations

import structlog

from app.core.redis import get_redis_client

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CANCEL_KEY_PREFIX = "bgjob:cancel:"
CANCEL_TTL_SECONDS = 3600


async def signal_cancel(job_id: str) -> None:
    redis = get_redis_client()
    try:
        await redis.set(
            f"{CANCEL_KEY_PREFIX}{job_id}",
            "1",
            ex=CANCEL_TTL_SECONDS,
        )
    except Exception:
        logger.exception("cancel_signal_failed", job_id=job_id)


async def is_cancelled(job_id: str) -> bool:
    redis = get_redis_client()
    try:
        val = await redis.get(f"{CANCEL_KEY_PREFIX}{job_id}")
    except Exception:
        return False
    return val is not None


async def clear_cancel(job_id: str) -> None:
    redis = get_redis_client()
    try:
        await redis.delete(f"{CANCEL_KEY_PREFIX}{job_id}")
    except Exception:
        pass
