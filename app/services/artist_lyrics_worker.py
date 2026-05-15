from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.artist import Artist, TrackArtist
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.services.lyrics_service import LyricsService
from app.services.lyrics_state import has_nonempty_synced_lines

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@broker.task
async def enqueue_artist_lyrics_task(
    artist_id: int,
    with_sync: bool = True,
    include_existing_text: bool = True,
    batch_size: int = 1000,
) -> dict[str, Any]:
    queued = 0
    skipped_existing = 0
    inspected = 0
    max_rows = max(1, min(int(batch_size), 5000))
    async with AsyncSessionLocal() as session:
        artist_exists = await session.scalar(
            select(Artist.id).where(Artist.id == artist_id).limit(1)
        )
        if artist_exists is None:
            raise ValueError("artist not found")

        rows = await session.execute(
            select(
                Track.id,
                TrackLyrics.plain_text,
                TrackLyrics.synced_lines,
            )
            .join(TrackArtist, TrackArtist.track_id == Track.id)
            .outerjoin(TrackLyrics, TrackLyrics.track_id == Track.id)
            .where(
                TrackArtist.artist_id == artist_id,
                Track.is_active.is_(True),
            )
            .order_by(Track.id.asc())
            .limit(max_rows)
        )
        items = list(rows.all())
        inspected = len(items)
        service = LyricsService(session)
        use_global_queue = settings.lyrics_global_orchestrator_enabled
        for track_id_raw, plain_text, synced_lines in items:
            track_id = int(track_id_raw)
            has_text = bool((plain_text or "").strip())
            has_sync = has_nonempty_synced_lines(synced_lines)
            force_sync = bool(
                with_sync
                and include_existing_text
                and has_text
                and not has_sync
            )
            if has_text and not force_sync:
                skipped_existing += 1
                continue
            if use_global_queue:
                from app.services import lyrics_global_orchestrator

                await lyrics_global_orchestrator.enqueue(
                    track_id,
                    with_sync=with_sync,
                    force_sync_existing_text=force_sync,
                )
                queued += 1
                continue
            progress_id = await service.enqueue_background_lyrics(
                track_id,
                requested_by_user_id=None,
                with_sync=with_sync,
                bypass_cache=False,
                force_sync_existing_text=force_sync,
            )
            if progress_id:
                queued += 1
            else:
                skipped_existing += 1
    summary = {
        "artist_id": artist_id,
        "inspected": inspected,
        "queued": queued,
        "skipped_existing": skipped_existing,
        "with_sync": with_sync,
        "include_existing_text": include_existing_text,
        "global_queue": bool(settings.lyrics_global_orchestrator_enabled),
    }
    logger.info("artist_lyrics_enqueue_done", **summary)
    return summary
