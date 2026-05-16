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
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqEvents, TaskiqState

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.services.import_service import EXTERNAL_IMPORT_SOURCES


def _supports_skip_locked(session: AsyncSession) -> bool:
    bind = session.get_bind()
    return getattr(bind.dialect, "name", "") == "postgresql"


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_WORKER_BG_TASK_STOP_TIMEOUT: float = 15.0

_dispatcher_task: asyncio.Task[None] | None = None


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


async def sweep_stuck_jobs() -> int:
    """Reset jobs that have been ``importing`` with no progress.

    A worker crash, restart, or hard kill can leave an ImportJob
    pinned to ``importing`` forever — it never receives the
    ``done``/``failed`` transition that would normally release the
    concurrency slot. We use ``ImportJob.updated_at`` as a free
    heartbeat: any commit inside the worker (per-track progress,
    cursor advance, status change) bumps it. If nothing has
    happened for ``import_job_stuck_after_seconds``, we assume the
    worker is gone and flip the row back to ``queued`` so the
    dispatcher promotes it again. The new worker resumes from
    ``tracks_data['cursor_index']`` and a fresh ``worker_lease``
    causes any zombie worker that later wakes up to abort cleanly.
    """
    threshold_seconds = int(settings.import_job_stuck_after_seconds)
    if threshold_seconds <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(seconds=threshold_seconds)
    async with AsyncSessionLocal() as session:
        stmt = (
            update(ImportJob)
            .where(
                ImportJob.status == "importing",
                ImportJob.updated_at < cutoff,
            )
            .values(status="queued")
            .returning(ImportJob.id)
        )
        result = await session.execute(stmt)
        ids = [int(row[0]) for row in result.all()]
        if ids:
            await session.commit()
            logger.warning(
                "import_dispatcher_swept_stuck_jobs",
                job_ids=ids,
                stuck_after_seconds=threshold_seconds,
            )
        return len(ids)


async def _requeue_import_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            return
        job.status = "queued"
        await session.commit()


async def dispatch_once() -> int:
    """Promote up to ``slots`` queued jobs into ``importing``.

    Returns the number of jobs actually promoted (0 when no slots
    were free or no queued jobs existed).
    """
    await sweep_stuck_jobs()
    promoted: list[ImportJob] = []
    async with AsyncSessionLocal() as session:
        global_active = await _count_active(session)
        slots = max(
            0,
            int(settings.import_max_concurrent_jobs) - global_active,
        )
        if slots == 0:
            return 0

        candidates_stmt = (
            select(ImportJob)
            .where(ImportJob.status == "queued")
            .order_by(ImportJob.created_at.asc())
            .limit(slots * 4)
        )
        if _supports_skip_locked(session):
            candidates_stmt = candidates_stmt.with_for_update(skip_locked=True)
        candidates_result = await session.execute(candidates_stmt)
        candidates = list(candidates_result.scalars().all())
        if not candidates:
            return 0

        per_user = await _per_user_active(session)
        per_user_cap = int(settings.import_per_user_max_concurrent)

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
            try:
                await _requeue_import_job(job.id)
            except Exception:
                logger.error(
                    "import_dispatcher_rollback_failed",
                    job_id=job.id,
                )
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


async def stop_dispatcher_task() -> None:
    global _dispatcher_task
    task = _dispatcher_task
    if task is None or task.done():
        _dispatcher_task = None
        return
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=_WORKER_BG_TASK_STOP_TIMEOUT)
    except TimeoutError:
        logger.warning("import_dispatcher_stop_timeout")
    except asyncio.CancelledError:
        pass
    finally:
        _dispatcher_task = None


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
