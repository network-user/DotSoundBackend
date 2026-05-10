"""Daily Taskiq job that hard-deletes tracks past grace period.

Wired into ``scheduled_jobs`` by alembic migration ``0087``. The
scheduler kicks this task once a day (cron ``0 4 * * *``).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services.track_hard_delete_service import (
    TrackHardDeleteService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@broker.task
async def hard_delete_expired_tracks_task() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = TrackHardDeleteService(session)
        summary = await svc.hard_delete_expired_tracks()
        await session.commit()
    logger.info("track_hard_delete_task_done", **summary)
    return summary
