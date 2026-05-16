from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from dotsound_private_core.services.compute_job_policy import (
    backoff_for_error_kind,
    should_fallback_to_local,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import LocalComputeJob
from app.services.compute_job_local_handlers import get_local_handler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

REAP_BATCH_LIMIT = 100


def _now() -> datetime:
    return datetime.now(UTC)


async def _mark_terminal_failed(
    session: AsyncSession,
    job: ComputeJob,
    *,
    reason: str,
) -> None:
    job.status = q.STATUS_FAILED
    job.finished_at = _now()
    job.last_error = reason[:1024]
    job.claimed_by = None
    job.claimed_at = None
    job.claim_deadline_at = None
    job.started_at = None
    await session.flush()


async def _requeue_with_policy_backoff(
    session: AsyncSession,
    job: ComputeJob,
    *,
    error_kind: str,
    reason: str,
) -> None:
    backoff = backoff_for_error_kind(
        error_kind,
        attempt=max(1, int(job.attempts)),
    )
    job.status = q.STATUS_PENDING
    job.next_attempt_at = _now() + timedelta(seconds=float(backoff))
    job.last_error = reason[:1024]
    job.claimed_by = None
    job.claimed_at = None
    job.claim_deadline_at = None
    job.started_at = None
    await session.flush()


async def _try_local_fallback(
    session: AsyncSession,
    job: ComputeJob,
) -> bool:
    handler = get_local_handler(job.job_type)
    if handler is None:
        return False
    local_job = LocalComputeJob.from_model(job)
    result = await handler(local_job)
    await q.mark_succeeded(
        session,
        job=job,
        result=result or {"status": "ok"},
    )
    logger.warning(
        "compute_job_local_fallback_succeeded",
        job_id=job.id,
        job_type=job.job_type,
        attempts=job.attempts,
    )
    return True


async def handle_worker_failure(
    session: AsyncSession,
    *,
    job: ComputeJob,
    error_kind: str,
    reason: str,
) -> str:
    canonical_type = q.canonical_job_type(job.job_type)
    reason_text = reason or error_kind or "job_failed"
    if error_kind == "dead_track":
        await _mark_terminal_failed(
            session,
            job,
            reason=reason_text,
        )
        return "failed_terminal"

    if should_fallback_to_local(
        canonical_type,
        failed_attempts=max(1, int(job.attempts)),
    ):
        if await _try_local_fallback(session, job):
            return "local_fallback"

    if int(job.attempts) >= int(job.max_attempts):
        await _mark_terminal_failed(
            session,
            job,
            reason=reason_text,
        )
        return "failed_terminal"

    await _requeue_with_policy_backoff(
        session,
        job,
        error_kind=error_kind or "worker_unreachable",
        reason=reason_text,
    )
    return "requeued"


async def reap_once(
    *,
    limit: int = REAP_BATCH_LIMIT,
) -> dict[str, int]:
    now = _now()
    stats: dict[str, int] = {
        "requeued": 0,
        "local_fallback": 0,
        "failed_terminal": 0,
    }
    async with AsyncSessionLocal() as session:
        jobs = (
            await session.execute(
                select(ComputeJob)
                .where(
                    ComputeJob.status == q.STATUS_CLAIMED,
                    ComputeJob.claim_deadline_at.is_not(None),
                    ComputeJob.claim_deadline_at < now,
                )
                .order_by(ComputeJob.claim_deadline_at.asc())
                .limit(int(limit))
            )
        ).scalars()
        for job in list(jobs):
            outcome = await handle_worker_failure(
                session,
                job=job,
                error_kind="lease_expired",
                reason="lease_expired",
            )
            stats[outcome] = stats.get(outcome, 0) + 1
        await session.commit()
    if any(stats.values()):
        logger.warning("compute_job_reaper_handled", **stats)
    return stats


__all__ = [
    "REAP_BATCH_LIMIT",
    "handle_worker_failure",
    "reap_once",
]
