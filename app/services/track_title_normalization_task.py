"""Retroactive title-artist normalization task."""

from __future__ import annotations

import structlog

from app.core.tkq import broker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@broker.task
async def normalize_track_titles_batch(
    offset: int = 0,
    batch_size: int = 200,
) -> dict:
    """Parse titles of existing tracks and link implied artists.

    Safe to run multiple times — link_track uses on_conflict_do_nothing.
    Chain subsequent batches manually or via the admin endpoint.
    """
    from sqlalchemy import func, select

    from app.core.db import AsyncSessionLocal
    from app.models.artist import TrackArtist
    from app.models.track import Track
    from app.services.artist_service import ArtistService
    from app.services.title_normalizer import parse_title

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track.id, Track.title)
            .where(Track.is_active.is_(True))
            .order_by(Track.id)
            .offset(offset)
            .limit(batch_size)
        )
        rows = result.all()
        if not rows:
            return {"processed": 0, "done": True, "offset": offset}

        svc = ArtistService(session)
        processed = 0
        skipped = 0

        for track_id, title in rows:
            if not title:
                skipped += 1
                continue
            parsed = parse_title(title)
            if parsed.is_empty():
                skipped += 1
                continue

            count_result = await session.execute(
                select(func.count()).where(TrackArtist.track_id == track_id)
            )
            existing_count = count_result.scalar() or 0

            try:
                await svc.link_title_artists(
                    track_id=track_id,
                    title=title,
                    existing_artist_count=existing_count,
                )
                processed += 1
            except Exception:
                logger.warning(
                    "normalize_track_titles_batch_error",
                    track_id=track_id,
                )
                skipped += 1

        await session.commit()

        done = len(rows) < batch_size
        logger.info(
            "normalize_track_titles_batch_done",
            offset=offset,
            processed=processed,
            skipped=skipped,
            done=done,
        )
        return {
            "processed": processed,
            "skipped": skipped,
            "offset": offset,
            "next_offset": offset + batch_size,
            "done": done,
        }
