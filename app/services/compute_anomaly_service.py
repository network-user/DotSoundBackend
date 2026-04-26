"""Anomaly detector for compute workers.

Decides nothing on its own — every threshold and every yes/no
verdict comes from
``dotsound_private_core.services.compute_anomaly_policy``. This
module just wires the policy to the live system: read counters
from Redis, write audit rows, suspend the worker, fire admin
alerts.

Hooks in two places today:

- `record_remote_result` is called from `mark_job_result` in
  `compute_worker_service` (and indirectly by the lease reaper
  when it wants to flag a stuck job).
- `record_failure` is called when a worker submits a `/fail`
  callback so we can track failure rate.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import structlog
from dotsound_private_core.services.compute_anomaly_policy import (
    ANOMALY_DUPLICATE_RESULT,
    ANOMALY_HIGH_FAILURE_RATE,
    ANOMALY_PROCESSING_TOO_FAST,
    DEFAULT_AUTO_SUSPEND_MINUTES,
    DEFAULT_FAILURE_RATE_MIN_SAMPLE,
    DEFAULT_FAILURE_RATE_THRESHOLD,
    DEFAULT_FLAG_THRESHOLD,
    DEFAULT_FLAG_WINDOW_SECONDS,
    is_duplicate_result,
    is_failure_rate_suspicious,
    is_processing_too_fast,
    should_auto_suspend,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

FLAG_KEY_PREFIX = "worker:anomaly_flags:"
RECENT_RESULT_KEY_PREFIX = "worker:recent_results:"
RECENT_RESULT_HISTORY = 50


def _flag_key(worker_id: str) -> str:
    return f"{FLAG_KEY_PREFIX}{worker_id}"


def _recent_result_key(worker_id: str) -> str:
    return f"{RECENT_RESULT_KEY_PREFIX}{worker_id}"


def _hash_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8", errors="ignore")
    ).hexdigest()


async def _record_flag(
    session: AsyncSession,
    *,
    worker_id: str,
    anomaly_type: str,
    job_id: str | None,
    details: dict,
) -> int:
    """Write the flag (audit + Redis counter), return current
    flag count inside the rolling window.
    """
    redis = get_redis_client()
    key = _flag_key(worker_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(
            key, DEFAULT_FLAG_WINDOW_SECONDS
        )
    await cws._log_audit(
        session,
        worker_id=worker_id,
        ip=None,
        action="anomaly",
        job_id=job_id,
        status_code=None,
        meta={
            "anomaly_type": anomaly_type,
            "details": details,
            "flags_in_window": int(count),
        },
    )
    try:
        from app.core.observability import (
            worker_anomaly_observed,
        )

        worker_anomaly_observed(
            anomaly_type=anomaly_type
        )
    except Exception:
        pass
    return int(count)


async def _maybe_auto_suspend(
    session: AsyncSession,
    *,
    worker_id: str,
    flags_in_window: int,
) -> None:
    if not should_auto_suspend(
        flags_in_window=flags_in_window,
        threshold=DEFAULT_FLAG_THRESHOLD,
    ):
        return
    until = datetime.now(UTC) + timedelta(
        minutes=DEFAULT_AUTO_SUSPEND_MINUTES
    )
    repo = AudioComputeRepository(session)
    await repo.suspend_worker_until(
        worker_id,
        until,
        reason="anomaly_threshold",
    )
    await cws._log_audit(
        session,
        worker_id=worker_id,
        ip=None,
        action="auto_suspend",
        status_code=None,
        meta={
            "trigger": "anomaly_threshold",
            "until": until.isoformat(),
            "flags": flags_in_window,
        },
    )
    logger.warning(
        "worker_anomaly_auto_suspend",
        worker_id=worker_id,
        flags=flags_in_window,
        minutes=DEFAULT_AUTO_SUSPEND_MINUTES,
    )
    try:
        from app.services.admin_alert_service import (
            send_alert,
        )

        await send_alert(
            event_type="worker_auto_suspended",
            severity="warning",
            title=(
                f"Worker {worker_id} auto-suspended"
            ),
            details=(
                f"Anomaly threshold reached "
                f"({flags_in_window} flags in "
                f"{DEFAULT_FLAG_WINDOW_SECONDS}s). "
                f"Suspended until {until.isoformat()}."
            ),
        )
    except Exception:
        logger.debug(
            "anomaly_alert_dispatch_failed",
            worker_id=worker_id,
        )


async def _push_recent_result(
    worker_id: str, text_hash: str
) -> list[str]:
    redis = get_redis_client()
    key = _recent_result_key(worker_id)
    await redis.lpush(key, text_hash)
    await redis.ltrim(key, 0, RECENT_RESULT_HISTORY - 1)
    raw = await redis.lrange(
        key, 0, RECENT_RESULT_HISTORY - 1
    )
    return [
        item.decode() if isinstance(item, bytes) else item
        for item in raw
    ]


async def record_remote_result(
    session: AsyncSession,
    *,
    worker_id: str,
    job_id: str,
    audio_seconds: float,
    processing_seconds: float,
    plain_text: str,
) -> list[str]:
    """Run all anomaly checks for a successful worker result.

    Returns the list of anomaly_type strings that fired (empty
    list = clean job). The caller can include this in its audit
    payload for trace clarity.
    """
    fired: list[str] = []

    if is_processing_too_fast(
        audio_seconds=audio_seconds,
        processing_seconds=processing_seconds,
    ):
        count = await _record_flag(
            session,
            worker_id=worker_id,
            anomaly_type=(
                ANOMALY_PROCESSING_TOO_FAST
            ),
            job_id=job_id,
            details={
                "audio_seconds": audio_seconds,
                "processing_seconds": (
                    processing_seconds
                ),
            },
        )
        fired.append(ANOMALY_PROCESSING_TOO_FAST)
        await _maybe_auto_suspend(
            session,
            worker_id=worker_id,
            flags_in_window=count,
        )

    text_hash = (
        _hash_text(plain_text) if plain_text else ""
    )
    history = await _push_recent_result(
        worker_id, text_hash
    )
    if text_hash and is_duplicate_result(
        new_text_sha256=text_hash,
        recent_text_sha256=history[1:],
    ):
        count = await _record_flag(
            session,
            worker_id=worker_id,
            anomaly_type=ANOMALY_DUPLICATE_RESULT,
            job_id=job_id,
            details={"text_sha256": text_hash},
        )
        fired.append(ANOMALY_DUPLICATE_RESULT)
        await _maybe_auto_suspend(
            session,
            worker_id=worker_id,
            flags_in_window=count,
        )

    return fired


async def record_failure(
    session: AsyncSession,
    *,
    worker_id: str,
    job_id: str | None,
    total_recent_jobs: int,
    failed_recent_jobs: int,
) -> bool:
    """Check failure rate after a worker reports a /fail. Returns
    True if the rate triggered a flag.
    """
    if not is_failure_rate_suspicious(
        total_jobs=total_recent_jobs,
        failed_jobs=failed_recent_jobs,
        threshold_ratio=DEFAULT_FAILURE_RATE_THRESHOLD,
        min_sample=DEFAULT_FAILURE_RATE_MIN_SAMPLE,
    ):
        return False
    count = await _record_flag(
        session,
        worker_id=worker_id,
        anomaly_type=ANOMALY_HIGH_FAILURE_RATE,
        job_id=job_id,
        details={
            "total": total_recent_jobs,
            "failed": failed_recent_jobs,
        },
    )
    await _maybe_auto_suspend(
        session,
        worker_id=worker_id,
        flags_in_window=count,
    )
    return True


__all__ = [
    "record_failure",
    "record_remote_result",
]
