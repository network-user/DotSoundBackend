"""Lease reaper: drives stuck `running` lyrics jobs to either
the next cascade tier or to a hard failure.

A job is considered stuck when ``deadline_at < now()`` while its
status is still ``running``. The reaper hands the job over to
``lyrics_cascade.handle_lease_expired`` which is the single
authority on tier transitions.

Intended cadence: once a minute. Run via the bundled CLI helper
or by enqueueing ``reap_expired_jobs_task`` on a Taskiq schedule.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

REAP_BATCH_LIMIT = 50
REAP_INTERVAL_SECONDS = 60


async def reap_once() -> int:
    """Reap expired jobs in one pass; returns count handled."""
    handled = 0
    async with AsyncSessionLocal() as session:
        repo = AudioComputeRepository(session)
        now = datetime.now(UTC)
        expired = await repo.list_expired_running_jobs(
            now=now, limit=REAP_BATCH_LIMIT
        )
        if not expired:
            return 0
        for job in expired:
            try:
                from app.services.lyrics_cascade import (
                    handle_lease_expired,
                )

                will_fallback = await handle_lease_expired(
                    session, job=job
                )
            except ImportError:
                will_fallback = False
            if not will_fallback:
                await cws.mark_job_failed(
                    session,
                    job=job,
                    reason="lease_expired",
                )
            await cws._log_audit(
                session,
                worker_id=job.routed_to_worker,
                ip=None,
                action="lease_expired",
                job_id=job.id,
                status_code=410,
                meta={
                    "deadline_at": (
                        job.deadline_at.isoformat()
                        if job.deadline_at
                        else None
                    ),
                    "fallback": bool(will_fallback),
                },
            )
            handled += 1
        await session.commit()
    if handled:
        logger.warning(
            "lease_reaper_handled_jobs",
            count=handled,
        )
    return handled


@broker.task
async def reap_expired_jobs_task() -> dict:
    """Taskiq entrypoint for the lease reaper."""
    handled = await reap_once()
    return {"handled": int(handled)}


async def run_forever() -> None:
    """Local dev helper: run the reaper in a tight loop.

    Production should use ``taskiq scheduler`` or a systemd timer
    to enqueue ``reap_expired_jobs_task`` instead.
    """
    while True:
        try:
            await reap_once()
        except Exception:
            logger.exception("lease_reaper_failed")
        await asyncio.sleep(REAP_INTERVAL_SECONDS)


__all__ = [
    "REAP_BATCH_LIMIT",
    "REAP_INTERVAL_SECONDS",
    "reap_once",
    "reap_expired_jobs_task",
    "run_forever",
]
