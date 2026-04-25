"""Backfill track_artists for all tracks that have artist text but no links.

Usage:
    poetry run python scripts/backfill_artist_links.py           # dry-run
    poetry run python scripts/backfill_artist_links.py --apply   # write to DB
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.artist import TrackArtist
from app.models.track import Track
from app.services.artist_service import ArtistService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def backfill(apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track.id, Track.artist, Track.source_platform)
            .where(Track.artist.isnot(None))
            .where(Track.is_active.is_(True))
            .order_by(Track.id)
        )
        rows = result.all()

        already_linked = set(
            (await session.execute(
                select(TrackArtist.track_id).distinct()
            )).scalars().all()
        )

        candidates = [
            (tid, art, sp)
            for tid, art, sp in rows
            if tid not in already_linked and art
        ]

        print(
            f"Tracks with artist field: {len(rows)}, "
            f"already linked: {len(already_linked)}, "
            f"to backfill: {len(candidates)}"
        )

        if not apply:
            print("Dry-run — pass --apply to write changes.")
            return

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
                    print(f"  {ok} linked…")
            except Exception as exc:
                failed += 1
                logger.warning(
                    "backfill_artist_link_failed",
                    track_id=track_id,
                    error=str(exc),
                )

        await session.commit()
        print(f"Done. Linked: {ok}, failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to DB (default: dry-run)",
    )
    args = parser.parse_args()
    asyncio.run(backfill(args.apply))
