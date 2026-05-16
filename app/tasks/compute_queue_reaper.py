"""Compute-queue reaper: returns stale `claimed` jobs to `pending`.

A compute_job is considered stale when its ``claim_deadline_at``
has passed while its status is still ``claimed`` — typically
because the worker that claimed it crashed before reporting back.

Intended cadence: once a minute. Run via Taskiq schedule
(``reap_stale_compute_jobs_task``) or via the local-dev helper
``run_forever``.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.tkq import broker
from app.services import compute_job_reaper

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

REAP_BATCH_LIMIT = compute_job_reaper.REAP_BATCH_LIMIT
REAP_INTERVAL_SECONDS = 60


async def reap_once() -> dict[str, int]:
    """Recover stale claims in one pass; returns outcome counters."""
    stats = await compute_job_reaper.reap_once(limit=REAP_BATCH_LIMIT)
    if any(stats.values()):
        logger.warning(
            "compute_queue_reaper_recovered",
            **stats,
        )
    return stats


@broker.task
async def reap_stale_compute_jobs_task() -> dict:
    """Taskiq entrypoint for the compute-queue reaper."""
    return await reap_once()


async def run_forever() -> None:
    while True:
        try:
            await reap_once()
        except Exception:
            logger.exception("compute_queue_reaper_failed")
        await asyncio.sleep(REAP_INTERVAL_SECONDS)


__all__ = [
    "REAP_BATCH_LIMIT",
    "REAP_INTERVAL_SECONDS",
    "reap_once",
    "reap_stale_compute_jobs_task",
    "run_forever",
]
