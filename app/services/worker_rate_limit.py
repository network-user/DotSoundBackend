"""Per-worker rate limiting + strike-based auto-suspend.

slowapi keys by client IP, which is wrong for our pull workers
(many requests from one trusted host). We instead key by
``X-Worker-Id`` and enforce explicit per-action quotas. After N
strikes in a sliding window we suspend the worker for M minutes
via `AudioComputeRepository.suspend_worker_until`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

DEFAULT_LIMITS_PER_MIN: dict[str, int] = {
    "heartbeat": 12,
    "claim": 30,
    "result": 30,
    "progress": 60,
    "fail": 30,
    "audio": 10,
}

STRIKE_KEY_PREFIX = "worker:rl_strikes:"
LIMIT_KEY_PREFIX = "worker:rl:"
STRIKE_WINDOW_SECONDS = 600
STRIKE_THRESHOLD = 3
SUSPEND_MINUTES_AFTER_STRIKES = 5


class WorkerRateLimitExceeded(Exception):
    """Raised when a worker exceeds the per-action minute quota."""

    def __init__(
        self,
        action: str,
        limit: int,
        suspended: bool = False,
    ) -> None:
        super().__init__(
            f"rate_limit_exceeded:{action}:{limit}/min"
        )
        self.action = action
        self.limit = limit
        self.suspended = suspended


async def check_and_consume(
    session: AsyncSession,
    *,
    worker_id: str,
    action: str,
    audit_ip: str | None = None,
) -> None:
    """Atomically increment the per-minute counter for
    ``(worker_id, action)``. Raises ``WorkerRateLimitExceeded``
    when the quota is busted; on the 3rd strike inside a 10-min
    window the worker is also suspended for 5 minutes and the
    exception's ``suspended`` flag is True so the caller can write
    a richer audit entry.
    """
    limit = DEFAULT_LIMITS_PER_MIN.get(action)
    if not limit:
        return

    redis = get_redis_client()
    now = datetime.now(timezone.utc)
    bucket = now.strftime("%Y%m%d%H%M")
    key = (
        f"{LIMIT_KEY_PREFIX}{worker_id}:{action}:{bucket}"
    )
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 70)
    if current <= limit:
        return

    strike_key = f"{STRIKE_KEY_PREFIX}{worker_id}"
    strikes = await redis.incr(strike_key)
    if strikes == 1:
        await redis.expire(
            strike_key, STRIKE_WINDOW_SECONDS
        )

    suspended = False
    if strikes >= STRIKE_THRESHOLD:
        until = now + timedelta(
            minutes=SUSPEND_MINUTES_AFTER_STRIKES
        )
        repo = AudioComputeRepository(session)
        await repo.suspend_worker_until(
            worker_id,
            until,
            reason="rate_limit_strikes",
        )
        await cws._log_audit(
            session,
            worker_id=worker_id,
            ip=audit_ip,
            action="auto_suspend",
            status_code=429,
            meta={
                "trigger": "rate_limit_strikes",
                "strikes": int(strikes),
                "until": until.isoformat(),
                "minutes": SUSPEND_MINUTES_AFTER_STRIKES,
            },
        )
        await session.commit()
        suspended = True
        logger.warning(
            "worker_auto_suspended",
            worker_id=worker_id,
            reason="rate_limit_strikes",
            strikes=int(strikes),
            minutes=SUSPEND_MINUTES_AFTER_STRIKES,
        )
    else:
        await cws._log_audit(
            session,
            worker_id=worker_id,
            ip=audit_ip,
            action="rate_limit_exceeded",
            status_code=429,
            meta={
                "limit": limit,
                "action_limited": action,
                "strikes": int(strikes),
            },
        )
        await session.commit()

    raise WorkerRateLimitExceeded(
        action, limit, suspended=suspended
    )


__all__ = [
    "DEFAULT_LIMITS_PER_MIN",
    "STRIKE_THRESHOLD",
    "STRIKE_WINDOW_SECONDS",
    "SUSPEND_MINUTES_AFTER_STRIKES",
    "WorkerRateLimitExceeded",
    "check_and_consume",
]
