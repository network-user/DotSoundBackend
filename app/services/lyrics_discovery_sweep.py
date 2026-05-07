"""Periodic backlog: enqueue LyricsJob cascade for eligible tracks."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, exists, func, select

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.lyrics import TrackLyrics
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.services.lyrics_service import LyricsService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__,
)


async def sweep_once(*, batch_size: int = 40) -> dict[str, Any]:
    queued = 0
    inspected = 0
    stripped = func.trim(func.coalesce(TrackLyrics.plain_text, ""))
    async with AsyncSessionLocal() as session:
        active_job_sq = exists(
            select(LyricsJob.id).where(
                LyricsJob.track_id == Track.id,
                LyricsJob.status.in_(("queued", "running")),
            ),
        )
        q = (
            select(Track.id)
            .outerjoin(
                TrackLyrics,
                TrackLyrics.track_id == Track.id,
            )
            .where(
                Track.is_active.is_(True),
                Track.lyrics_catalog_miss_at.is_(None),
                ~active_job_sq,
            )
            .where(
                and_(
                    TrackLyrics.id.is_(None),
                )
                | and_(
                    TrackLyrics.id.isnot(None),
                    stripped == "",
                ),
            )
            .order_by(Track.created_at.asc())
            .limit(int(batch_size)),
        )
        result = await session.execute(q)
        ids = list({int(r) for r in result.scalars().all()})
        inspected = len(ids)
        for track_id in ids:
            svc = LyricsService(session)
            progress_id = await svc.enqueue_background_lyrics(
                track_id,
                requested_by_user_id=None,
                with_sync=True,
                bypass_cache=False,
            )
            if progress_id:
                queued += 1

    summary = {"inspected": inspected, "enqueued": queued}
    logger.info("lyrics_discovery_sweep", **summary)
    return summary


@broker.task
async def lyrics_discovery_sweep_task(
    batch_size: int = 40,
) -> dict[
    str,
    Any,
]:
    return await sweep_once(batch_size=batch_size)


__all__ = [
    "lyrics_discovery_sweep_task",
    "sweep_once",
]
