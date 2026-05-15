"""Periodic backlog: enqueue LyricsJob cascade for eligible tracks."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import exists, func, or_, select

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.lyrics import TrackLyrics
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.services.lyrics_service import LyricsService
from app.services.lyrics_state import has_nonempty_synced_lines

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
        missing_q = (
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
                or_(
                    TrackLyrics.id.is_(None),
                    stripped == "",
                )
            )
            .order_by(Track.created_at.asc())
            .limit(int(batch_size)),
        )
        missing_result = await session.execute(missing_q)
        candidates: list[tuple[int, bool]] = [
            (int(r), False) for r in missing_result.scalars().all()
        ]
        remaining = max(0, int(batch_size) - len(candidates))
        if remaining > 0:
            sync_q = (
                select(Track.id, TrackLyrics.synced_lines)
                .join(
                    TrackLyrics,
                    TrackLyrics.track_id == Track.id,
                )
                .where(
                    Track.is_active.is_(True),
                    TrackLyrics.synced_lines.is_(None),
                    stripped != "",
                    ~active_job_sq,
                )
                .order_by(TrackLyrics.updated_at.asc())
                .limit(remaining)
            )
            sync_result = await session.execute(sync_q)
            for track_id, synced_lines in sync_result.all():
                if not has_nonempty_synced_lines(synced_lines):
                    candidates.append((int(track_id), True))
        inspected = len(candidates)
        svc = LyricsService(session)
        for track_id, force_sync in candidates:
            progress_id = await svc.enqueue_background_lyrics(
                track_id,
                requested_by_user_id=None,
                with_sync=True,
                bypass_cache=False,
                force_sync_existing_text=force_sync,
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
