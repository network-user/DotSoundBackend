"""Monthly artist stats snapshot Taskiq task.

Schedule externally (e.g. system cron / Docker)::

    taskiq execute app.services.artist_stats_worker \
        snapshot_monthly_artist_stats_task
        -- '{}' --on "0 2 1 * *"

Or trigger manually from admin or CLI.
"""

from __future__ import annotations

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services.artist_stats_service import (
    ArtistStatsService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


@broker.task
async def snapshot_monthly_artist_stats_task() -> dict:
    async with AsyncSessionLocal() as session:
        svc = ArtistStatsService(session)
        saved = await svc.snapshot_all_artists()
        await session.commit()
    logger.info(
        "artist_stats_snapshot_task_done",
        artists_saved=saved,
    )
    return {"artists_saved": saved}
