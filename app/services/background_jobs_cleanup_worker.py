"""Nightly cleanup task for the ``background_jobs`` table.

Without periodic pruning the table grows unbounded — Taskiq runs
millions of jobs per week in steady state. Terminal rows (``done``,
``cancelled``, ``failed_terminal``) are useful for short-term audit
and the dispatcher panel timeseries, but stale entries past the
retention window are pure ballast.

Retention windows (current heuristic, change if you grow logs):

* ``done`` — keep 7 days (most common, fastest growth).
* ``cancelled`` — keep 2 days (usually noise).
* ``failed_terminal`` — keep 30 days (longest, debugging).
* ``failed`` — kept until they flip to ``failed_terminal`` or
  ``done`` after retry, so this task never touches them.

The task is idempotent and uses ``LIMIT`` per status so a single
sweep cannot starve PostgreSQL: each status removes at most
``MAX_DELETE_PER_STATUS`` rows per run. If the table is heavily
backlogged the schedule will whittle it down across runs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.background_job import BackgroundJob

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

RETENTION_DAYS: dict[str, int] = {
    "done": 7,
    "cancelled": 2,
    "failed_terminal": 30,
}
MAX_DELETE_PER_STATUS = 50_000


@broker.task
async def cleanup_background_jobs_task() -> dict[str, Any]:
    """Sweep terminal ``background_jobs`` rows past retention."""
    now = datetime.now(UTC)
    summary: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        for status, days in RETENTION_DAYS.items():
            cutoff = now - timedelta(days=days)
            id_rows = (
                (
                    await session.execute(
                        select(BackgroundJob.id)
                        .where(
                            BackgroundJob.status == status,
                            BackgroundJob.created_at < cutoff,
                        )
                        .limit(MAX_DELETE_PER_STATUS)
                    )
                )
                .scalars()
                .all()
            )
            if not id_rows:
                summary[status] = 0
                continue
            result = await session.execute(
                delete(BackgroundJob).where(
                    BackgroundJob.id.in_(list(id_rows))
                )
            )
            await session.commit()
            summary[status] = int(result.rowcount or 0)
    logger.info("background_jobs_cleanup_done", summary=summary)
    return {"status": "ok", "summary": summary}


DEFAULT_SCHEDULE = {
    "id": "default-background-jobs-cleanup",
    "name": "default-background-jobs-cleanup",
    "task_name": (
        "app.services.background_jobs_cleanup_worker:"
        "cleanup_background_jobs_task"
    ),
    "cron": "17 3 * * *",
    "queue": "default",
    "payload": None,
    "enabled": True,
}


async def ensure_default_cleanup_schedule() -> bool:
    """Idempotent: insert the default nightly cleanup schedule if absent.

    Returns True if the row was created, False if it already existed
    or insertion failed (e.g. because the ``scheduled_jobs`` table is
    not yet migrated). Designed to run in app lifespan startup; never
    raises.
    """
    try:
        from app.models.scheduled_job import ScheduledJob

        async with AsyncSessionLocal() as session:
            existing = await session.get(ScheduledJob, DEFAULT_SCHEDULE["id"])
            if existing is not None:
                return False
            row = ScheduledJob(
                id=DEFAULT_SCHEDULE["id"],
                name=DEFAULT_SCHEDULE["name"],
                task_name=DEFAULT_SCHEDULE["task_name"],
                queue=DEFAULT_SCHEDULE["queue"],
                cron=DEFAULT_SCHEDULE["cron"],
                payload=DEFAULT_SCHEDULE["payload"],
                enabled=bool(DEFAULT_SCHEDULE["enabled"]),
            )
            session.add(row)
            await session.commit()
            logger.info(
                "default_cleanup_schedule_seeded",
                schedule_id=DEFAULT_SCHEDULE["id"],
                cron=DEFAULT_SCHEDULE["cron"],
            )
            return True
    except Exception as exc:
        logger.warning(
            "default_cleanup_schedule_seed_failed",
            error=str(exc)[:200],
        )
        return False


__all__ = [
    "RETENTION_DAYS",
    "MAX_DELETE_PER_STATUS",
    "DEFAULT_SCHEDULE",
    "cleanup_background_jobs_task",
    "ensure_default_cleanup_schedule",
]
