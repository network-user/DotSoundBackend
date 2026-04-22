"""Background promotion of queued ImportJob rows to importing.

Stage 4 of the concurrency hardening plan. The HTTP route that
starts an import sets ``status='queued'`` whenever the global or
per-user concurrency cap is full. This module runs a single
asyncio loop inside the Taskiq worker process that periodically
checks for free slots and promotes the oldest queued jobs to
``importing``, then ``kiq``-s the appropriate worker task.

The loop is fault-tolerant: every promotion is wrapped in
``try/except``, the loop itself never raises, and a kiq failure
rolls the job back to ``queued`` so the next dispatch tick can
retry it.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqEvents, TaskiqState

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.services.import_service import EXTERNAL_IMPORT_SOURCES

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


_dispatcher_task: asyncio.Task | None = None


async def _count_active(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ImportJob)
        .where(ImportJob.status == "importing")
    )
    return int(result.scalar() or 0)


async def _per_user_active(
    session: AsyncSession,
) -> dict[int, int]:
    result = await session.execute(
        select(ImportJob.user_id, func.count())
        .where(ImportJob.status == "importing")
        .group_by(ImportJob.user_id)
    )
    out: dict[int, int] = {}
    for uid, cnt in result.all():
        out[int(uid)] = int(cnt)
    return out


async def _kiq_for_job(job: ImportJob) -> None:
    if job.source in EXTERNAL_IMPORT_SOURCES:
        from app.services.external_import_worker import (
            process_external_import_job,
        )

        await process_external_import_job.kiq(job.id)
    else:
        from app.services.import_worker import process_import_job

        await process_import_job.kiq(job.id)


async def dispatch_once() -> int:
    """Promote up to ``slots`` queued jobs into ``importing``.

    Returns the number of jobs actually promoted (0 when no slots
    were free or no queued jobs existed).
    """
    async with AsyncSessionLocal() as session:
        global_active = await _count_active(session)
        slots = max(
            0,
            int(settings.import_max_concurrent_jobs) - global_active,
        )
        if slots == 0:
            return 0

        candidates_result = await session.execute(
            select(ImportJob)
            .where(ImportJob.status == "queued")
            .order_by(ImportJob.created_at.asc())
            .limit(slots * 4)
        )
        candidates = list(candidates_result.scalars().all())
        if not candidates:
            return 0

        per_user = await _per_user_active(session)
        per_user_cap = int(settings.import_per_user_max_concurrent)

        promoted: list[ImportJob] = []
        for job in candidates:
            if len(promoted) >= slots:
                break
            uid = int(job.user_id)
            if per_user.get(uid, 0) >= per_user_cap:
                continue
            job.status = "importing"
            promoted.append(job)
            per_user[uid] = per_user.get(uid, 0) + 1
        await session.commit()

        for job in promoted:
            try:
                await _kiq_for_job(job)
                logger.info(
                    "import_dispatcher_promoted",
                    job_id=job.id,
                    source=job.source,
                )
            except Exception as exc:  # noqa: BLE001
                await session.refresh(job)
                job.status = "queued"
                await session.commit()
                logger.error(
                    "import_dispatcher_kiq_failed",
                    job_id=job.id,
                    error=str(exc),
                )
        return len(promoted)


async def _dispatcher_loop() -> None:
    interval = float(settings.import_queue_dispatch_interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval)
            count = await dispatch_once()
            if count:
                logger.info(
                    "import_dispatcher_tick",
                    promoted=count,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("import_dispatcher_failed")


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start_dispatcher(_state: TaskiqState) -> None:
    global _dispatcher_task
    if _dispatcher_task is None or _dispatcher_task.done():
        _dispatcher_task = asyncio.create_task(_dispatcher_loop())
        logger.info(
            "import_dispatcher_started",
            interval_seconds=(settings.import_queue_dispatch_interval_seconds),
            max_concurrent=settings.import_max_concurrent_jobs,
            per_user_max=(settings.import_per_user_max_concurrent),
        )
