"""Remove bogus seed-artist links for tracks that only live in
artist «similar» stations.

Before the fix in ``app/services/artist_catalog_sync_service.py``
the station sync linked every station track to the seed artist
via ``track_artists``. That polluted
``GET /artists/{seed_id}/tracks`` with foreign artists' songs
(e.g. opening Giza's page showed tracks by рецидив / ybwackem / ...).

This script removes link rows ``(seed_artist_id, track_id)`` when:

  * ``track_id`` belongs to one of seed_artist's station releases
    (``release_kind = 'dotsound_sc_artist_station'``), AND
  * the track is NOT in any of seed_artist's *non-station*
    releases (so we don't accidentally unlink a track that the
    artist also has in a real album), AND
  * the track's own ``Track.artist`` string normalizes to a name
    different from the seed artist's normalized name.

Usage:
    poetry run python scripts/cleanup_station_artist_links.py
    poetry run python scripts/cleanup_station_artist_links.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog
from dotsound_private_core.services.artist_normalizer import (
    normalize_name,
)
from sqlalchemy import and_, delete, distinct, or_, select

from app.core.db import AsyncSessionLocal
from app.models.artist import Artist, TrackArtist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_STATION_KIND = "dotsound_sc_artist_station"


async def cleanup(apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        seed_ids = (
            (
                await session.execute(
                    select(distinct(ArtistCatalogRelease.artist_id)).where(
                        ArtistCatalogRelease.release_kind == _STATION_KIND
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"Artists with a station release: {len(seed_ids)}")

        total_removed = 0
        for seed_id in seed_ids:
            seed = await session.get(Artist, seed_id)
            if seed is None:
                continue

            station_track_ids = (
                (
                    await session.execute(
                        select(distinct(ArtistCatalogReleaseTrack.track_id))
                        .join(
                            ArtistCatalogRelease,
                            ArtistCatalogRelease.id
                            == ArtistCatalogReleaseTrack.release_id,
                        )
                        .where(
                            ArtistCatalogRelease.artist_id == seed_id,
                            ArtistCatalogRelease.release_kind == _STATION_KIND,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not station_track_ids:
                continue

            album_track_ids = set(
                (
                    await session.execute(
                        select(distinct(ArtistCatalogReleaseTrack.track_id))
                        .join(
                            ArtistCatalogRelease,
                            ArtistCatalogRelease.id
                            == ArtistCatalogReleaseTrack.release_id,
                        )
                        .where(
                            ArtistCatalogRelease.artist_id == seed_id,
                            or_(
                                ArtistCatalogRelease.release_kind.is_(None),
                                ArtistCatalogRelease.release_kind
                                != _STATION_KIND,
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )

            station_only = [
                tid for tid in station_track_ids if tid not in album_track_ids
            ]
            if not station_only:
                continue

            rows = (
                await session.execute(
                    select(Track.id, Track.artist).where(
                        Track.id.in_(station_only),
                    )
                )
            ).all()

            seed_norm = seed.name_normalized or normalize_name(seed.name)
            to_unlink: list[int] = []
            for tid, raw_artist in rows:
                if not raw_artist:
                    continue
                if normalize_name(raw_artist) == seed_norm:
                    continue
                to_unlink.append(tid)

            if not to_unlink:
                continue

            print(
                f"  seed_artist_id={seed_id} ({seed.name}): "
                f"would unlink {len(to_unlink)} bogus station tracks"
            )
            total_removed += len(to_unlink)

            if apply:
                await session.execute(
                    delete(TrackArtist).where(
                        and_(
                            TrackArtist.artist_id == seed_id,
                            TrackArtist.track_id.in_(to_unlink),
                        )
                    )
                )
                await session.commit()

        print(
            f"\nTotal bogus links {'removed' if apply else 'to remove'}: "
            f"{total_removed}"
        )
        if not apply:
            print("Dry-run. Pass --apply to actually delete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write deletes to DB (default: dry-run).",
    )
    args = parser.parse_args()
    asyncio.run(cleanup(args.apply))
