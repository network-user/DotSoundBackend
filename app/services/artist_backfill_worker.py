from __future__ import annotations

import structlog
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.artist import TrackArtist
from app.models.track import Track
from app.repositories.app_settings import AppSettingsRepository
from app.services.artist_service import ArtistService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SETTING_KEY = "migration.artist_link_backfill_v1"


@broker.task
async def artist_link_backfill_task() -> None:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Track.id, Track.artist, Track.source_platform)
                .where(
                    Track.artist.isnot(None),
                    Track.is_active.is_(True),
                )
                .order_by(Track.id)
            )
        ).all()

        already_linked: set[int] = set(
            (
                await session.execute(
                    select(TrackArtist.track_id).distinct()
                )
            ).scalars().all()
        )

        candidates = [
            (tid, art, sp)
            for tid, art, sp in rows
            if tid not in already_linked and art
        ]

        logger.info(
            "artist_link_backfill_started",
            total=len(rows),
            already_linked=len(already_linked),
            to_backfill=len(candidates),
        )

        svc = ArtistService(session)
        ok = 0
        failed = 0
        for track_id, artist_str, source_platform in candidates:
            try:
                await svc.resolve_and_link(
                    track_id=track_id,
                    raw_artist_string=artist_str,
                    source=source_platform or "internal",
                )
                ok += 1
                if ok % 100 == 0:
                    await session.commit()
                    logger.debug("artist_link_backfill_progress", linked=ok)
            except Exception:
                failed += 1
                logger.warning(
                    "artist_link_backfill_track_failed",
                    track_id=track_id,
                )

        await session.commit()

        repo = AppSettingsRepository(session)
        await repo.upsert(
            key=_SETTING_KEY,
            value={"done": True, "linked": ok, "failed": failed},
            updated_by=None,
        )
        await session.commit()
        logger.info(
            "artist_link_backfill_done", linked=ok, failed=failed
        )
