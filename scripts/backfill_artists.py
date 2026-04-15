"""Backfill Artist entities from existing Track.artist strings.

Usage:
    poetry run python scripts/backfill_artists.py
"""

import asyncio

import structlog
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.artist import TrackArtist
from app.models.track import Track
from app.services.artist_service import ArtistService

logger = structlog.get_logger(__name__)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        svc = ArtistService(session)
        result = await session.execute(
            select(Track).where(
                Track.artist.isnot(None),
                Track.artist != "",
                Track.is_active.is_(True),
                ~Track.id.in_(
                    select(TrackArtist.track_id)
                ),
            )
        )
        tracks = list(result.scalars().all())
        logger.info(
            "backfill_start",
            count=len(tracks),
        )

        for track in tracks:
            if not track.artist:
                continue
            linked = await svc.resolve_and_link(
                track_id=track.id,
                raw_artist_string=track.artist,
                source=track.source,
            )
            logger.info(
                "backfill_track",
                track_id=track.id,
                artist_raw=track.artist,
                linked=[a.name for a in linked],
            )

        await session.commit()
        logger.info("backfill_done")


if __name__ == "__main__":
    asyncio.run(main())
