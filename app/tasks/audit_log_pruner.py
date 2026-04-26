"""Daily prune of `worker_audit_log`.

Retention is a static policy: 90 days. The Backend exposes the
audit log to the admin UI for operational debugging; older rows
are removed to keep the table fast and to limit data exposure
if the DB dump leaks.

Cadence: once a day. Like the lease reaper, this lives as a
plain Taskiq task; production deployments enqueue it from
``taskiq scheduler`` or a systemd timer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.audio_compute import (
    AudioComputeRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

DEFAULT_RETENTION_DAYS = 90


async def prune_once(
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(
        days=int(retention_days)
    )
    async with AsyncSessionLocal() as session:
        repo = AudioComputeRepository(session)
        deleted = await repo.prune_audit_older_than(cutoff)
        await session.commit()
    logger.info(
        "audit_log_pruned",
        retention_days=retention_days,
        deleted=deleted,
        cutoff=cutoff.isoformat(),
    )
    return deleted


@broker.task
async def prune_worker_audit_log_task(
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> dict:
    deleted = await prune_once(retention_days)
    return {"deleted": int(deleted)}


__all__ = [
    "DEFAULT_RETENTION_DAYS",
    "prune_once",
    "prune_worker_audit_log_task",
]
