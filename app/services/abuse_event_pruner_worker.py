"""Daily Taskiq job that prunes ``abuse_events`` older than retention.

Retention window comes from PrivateCore
(``abuse_fingerprint_policy.ABUSE_EVENT_RETENTION_SECONDS``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.abuse_event import AbuseEventRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


@broker.task
async def prune_abuse_events_task() -> dict[str, Any]:
    from app.services.abuse_fingerprint_adapter import (
        ABUSE_EVENT_RETENTION_SECONDS,
    )

    cutoff = datetime.now(UTC) - timedelta(
        seconds=ABUSE_EVENT_RETENTION_SECONDS
    )
    async with AsyncSessionLocal() as session:
        repo = AbuseEventRepository(session)
        deleted = await repo.prune_older_than(cutoff=cutoff)
        await session.commit()
    summary = {
        "deleted": deleted,
        "cutoff": cutoff.isoformat(),
    }
    logger.info("abuse_events_pruned", **summary)
    return summary
