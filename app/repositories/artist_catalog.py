from datetime import UTC, date, datetime, timedelta
from typing import Literal

from dotsound_private_core.services.similarity_signal_policy import (
    build_similar_artist_weight_map,
    ordered_similar_artist_ids,
)
from sqlalchemy import and_, delete, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import TrackArtist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track
from app.repositories.base import BaseRepository

_ARTIST_STATION_KIND = "dotsound_sc_artist_station"


class ArtistCatalogRepository(BaseRepository[ArtistCatalogRelease]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ArtistCatalogRelease)

    async def get_by_artist_and_sc_album(
        self,
        artist_id: int,
        soundcloud_album_id: int,
    ) -> ArtistCatalogRelease | None:
        result = await self._session.execute(
            select(ArtistCatalogRelease).where(
                ArtistCatalogRelease.artist_id == artist_id,
                ArtistCatalogRelease.soundcloud_album_id
                == soundcloud_album_id,
            )
        )
        return result.scalar_one_or_none()

    async def latest_synced_at_for_artist(
        self,
        artist_id: int,
    ) -> datetime | None:
        stmt = select(func.max(ArtistCatalogRelease.synced_at)).where(
            and_(
                ArtistCatalogRelease.artist_id == artist_id,
                ArtistCatalogRelease.soundcloud_album_id.isnot(None),
            ),
        )
        raw = await self._session.scalar(stmt)
        if raw is None:
            return None
        return raw

    async def next_display_position(self, artist_id: int) -> int:
        raw = await self._session.scalar(
            select(func.max(ArtistCatalogRelease.display_position)).where(
                ArtistCatalogRelease.artist_id == artist_id
            )
        )
        if raw is None:
            return 0
        return int(raw) + 1

    async def upsert_release(
        self,
        artist_id: int,
        soundcloud_album_id: int,
        *,
        title: str,
        release_kind: str | None,
        released_at: date | None,
        cover_key: str | None,
        display_position: int,
    ) -> ArtistCatalogRelease:
        now = datetime.now(UTC)
        existing = await self.get_by_artist_and_sc_album(
            artist_id,
            soundcloud_album_id,
        )
        title_safe = title[:512]
        kind_safe = (
            release_kind[:32]
            if release_kind is not None and release_kind != ""
            else None
        )
        if existing:
            existing.title = title_safe
            existing.release_kind = kind_safe
            existing.released_at = released_at
            existing.display_position = display_position
            existing.synced_at = now
            if cover_key is not None:
                existing.cover_key = cover_key
            await self._session.flush()
            return existing
        rel = ArtistCatalogRelease(
            artist_id=artist_id,
            title=title_safe,
            release_kind=kind_safe,
            cover_key=cover_key,
            released_at=released_at,
            soundcloud_album_id=soundcloud_album_id,
            display_position=display_position,
            manual_lock=False,
            synced_at=now,
        )
        self._session.add(rel)
        await self._session.flush()
        return rel

    async def replace_release_tracks(
        self,
        release_id: int,
        ordered_track_ids: list[int],
    ) -> None:
        await self._session.execute(
            delete(ArtistCatalogReleaseTrack).where(
                ArtistCatalogReleaseTrack.release_id == release_id
            )
        )
        for pos, tid in enumerate(ordered_track_ids):
            self._session.add(
                ArtistCatalogReleaseTrack(
                    release_id=release_id,
                    track_id=tid,
                    position=pos,
                )
            )
        await self._session.flush()

    async def list_releases_with_track_counts(
        self,
        artist_id: int,
    ) -> list[tuple[ArtistCatalogRelease, int]]:
        cnt = func.count(ArtistCatalogReleaseTrack.id).label("track_count")
        stmt = (
            select(ArtistCatalogRelease, cnt)
            .outerjoin(
                ArtistCatalogReleaseTrack,
                ArtistCatalogReleaseTrack.release_id
                == ArtistCatalogRelease.id,
            )
            .where(ArtistCatalogRelease.artist_id == artist_id)
            .group_by(ArtistCatalogRelease.id)
            .order_by(
                ArtistCatalogRelease.display_position,
                ArtistCatalogRelease.id,
            )
        )
        result = await self._session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def get_release_for_artist(
        self,
        artist_id: int,
        release_id: int,
    ) -> ArtistCatalogRelease | None:
        stmt = select(ArtistCatalogRelease).where(
            ArtistCatalogRelease.id == release_id,
            ArtistCatalogRelease.artist_id == artist_id,
        )
        row = await self._session.execute(stmt)
        return row.scalar_one_or_none()

    async def get_release_tracks_ordered(
        self,
        release_id: int,
    ) -> list[tuple[int, Track]]:
        stmt = (
            select(
                ArtistCatalogReleaseTrack.position,
                Track,
            )
            .join(
                Track,
                Track.id == ArtistCatalogReleaseTrack.track_id,
            )
            .where(
                ArtistCatalogReleaseTrack.release_id == release_id,
            )
            .order_by(ArtistCatalogReleaseTrack.position)
        )
        rows = await self._session.execute(stmt)
        return [(int(p), t) for p, t in rows.all()]

    async def get_release_with_tracks_for_artist(
        self,
        artist_id: int,
        release_id: int,
    ) -> tuple[ArtistCatalogRelease, list[tuple[int, Track]]] | None:
        rel = await self.get_release_for_artist(
            artist_id,
            release_id,
        )
        if rel is None:
            return None
        tracks = await self.get_release_tracks_ordered(release_id)
        return rel, tracks

    async def create_manual_release(
        self,
        artist_id: int,
        *,
        title: str,
        release_kind: str | None,
        released_at: date | None,
        soundcloud_album_id: int | None,
        manual_lock: bool,
        cover_key: str | None,
    ) -> ArtistCatalogRelease:
        now = datetime.now(UTC)
        pos = await self.next_display_position(artist_id)
        title_safe = title[:512]
        kind_safe = (
            release_kind[:32]
            if release_kind is not None and release_kind != ""
            else None
        )
        if soundcloud_album_id is not None:
            clash = await self.get_by_artist_and_sc_album(
                artist_id,
                soundcloud_album_id,
            )
            if clash is not None:
                msg = "release with this soundcloud_album_id exists"
                raise ValueError(msg)
        rel = ArtistCatalogRelease(
            artist_id=artist_id,
            title=title_safe,
            release_kind=kind_safe,
            cover_key=cover_key,
            released_at=released_at,
            soundcloud_album_id=soundcloud_album_id,
            display_position=pos,
            manual_lock=manual_lock,
            synced_at=now,
        )
        self._session.add(rel)
        await self._session.flush()
        return rel

    async def delete_release_for_artist(
        self,
        artist_id: int,
        release_id: int,
    ) -> bool:
        rel = await self.get_release_for_artist(artist_id, release_id)
        if rel is None:
            return False
        await self._session.delete(rel)
        await self._session.flush()
        return True

    async def get_station_synced_at(
        self,
        artist_id: int,
    ) -> datetime | None:
        stmt = select(ArtistCatalogRelease.synced_at).where(
            ArtistCatalogRelease.artist_id == artist_id,
            ArtistCatalogRelease.release_kind
            == _ARTIST_STATION_KIND,
        )
        return await self._session.scalar(stmt)

    async def get_coartist_overlap_counts(
        self,
        seed_artist_ids: list[int],
        *,
        scope: Literal["station", "album"],
    ) -> dict[int, int]:
        if not seed_artist_ids:
            return {}
        release_station = (
            ArtistCatalogRelease.release_kind == _ARTIST_STATION_KIND
        )
        release_album = or_(
            ArtistCatalogRelease.release_kind.is_(None),
            ArtistCatalogRelease.release_kind != _ARTIST_STATION_KIND,
        )
        scope_clause = (
            release_station if scope == "station" else release_album
        )
        cnt = func.count(
            distinct(ArtistCatalogReleaseTrack.track_id),
        ).label("overlap_cnt")
        stmt = (
            select(
                TrackArtist.artist_id,
                cnt,
            )
            .join(
                ArtistCatalogReleaseTrack,
                ArtistCatalogReleaseTrack.track_id
                == TrackArtist.track_id,
            )
            .join(
                ArtistCatalogRelease,
                ArtistCatalogRelease.id
                == ArtistCatalogReleaseTrack.release_id,
            )
            .where(
                ArtistCatalogRelease.artist_id.in_(
                    seed_artist_ids
                ),
                TrackArtist.artist_id.not_in(
                    seed_artist_ids
                ),
                scope_clause,
            )
            .group_by(TrackArtist.artist_id)
        )
        rows = await self._session.execute(stmt)
        return {
            int(aid): int(c)
            for aid, c in rows.all()
            if aid is not None and c is not None
        }

    async def get_station_neighbor_track_ids_for_artists(
        self,
        seed_artist_ids: list[int],
        *,
        exclude_track_ids: frozenset[int],
        limit: int,
    ) -> list[int]:
        if not seed_artist_ids or limit <= 0:
            return []
        stmt = (
            select(ArtistCatalogReleaseTrack.track_id)
            .join(
                ArtistCatalogRelease,
                ArtistCatalogRelease.id
                == ArtistCatalogReleaseTrack.release_id,
            )
            .where(
                ArtistCatalogRelease.artist_id.in_(
                    seed_artist_ids
                ),
                ArtistCatalogRelease.release_kind
                == _ARTIST_STATION_KIND,
            )
            .distinct()
            .limit(limit)
        )
        if exclude_track_ids:
            stmt = stmt.where(
                ArtistCatalogReleaseTrack.track_id.not_in(
                    exclude_track_ids
                )
            )
        rows = await self._session.execute(stmt)
        return [int(r) for (r,) in rows.all() if r is not None]

    async def get_similar_artist_recommendation_signals(
        self,
        seed_artist_ids: list[int],
    ) -> tuple[list[int], dict[int, float]]:
        if not seed_artist_ids:
            return [], {}
        station = await self.get_coartist_overlap_counts(
            seed_artist_ids,
            scope="station",
        )
        album = await self.get_coartist_overlap_counts(
            seed_artist_ids,
            scope="album",
        )
        weights = build_similar_artist_weight_map(station, album)
        return ordered_similar_artist_ids(weights), weights

    async def get_similar_artist_ids_from_stations(
        self,
        artist_ids: list[int],
    ) -> list[int]:
        ids, _ = await self.get_similar_artist_recommendation_signals(
            artist_ids,
        )
        return ids

    async def find_stale_station_artist_ids(
        self,
        threshold_days: int,
    ) -> list[int]:
        """Artists whose SC station row is stale or missing."""
        cutoff = datetime.now(UTC) - timedelta(days=threshold_days)
        stmt = (
            select(distinct(ArtistCatalogRelease.artist_id))
            .where(
                ArtistCatalogRelease.release_kind
                == _ARTIST_STATION_KIND,
                (ArtistCatalogRelease.synced_at.is_(None))
                | (ArtistCatalogRelease.synced_at < cutoff),
            )
        )
        rows = await self._session.execute(stmt)
        return [r for (r,) in rows.all()]

    async def find_stale_full_catalog_artist_ids(
        self,
        threshold_days: int,
        *,
        limit: int = 50,
    ) -> list[int]:
        """Artists with SC identity whose non-station catalog is stale or
        missing entirely. Used by the periodic full-catalog sweep task."""
        from app.models.artist import Artist

        cutoff = datetime.now(UTC) - timedelta(days=threshold_days)
        last_sync_sq = (
            select(
                ArtistCatalogRelease.artist_id.label("artist_id"),
                func.max(ArtistCatalogRelease.synced_at).label(
                    "last_sync"
                ),
            )
            .where(
                ArtistCatalogRelease.release_kind
                != _ARTIST_STATION_KIND,
                ArtistCatalogRelease.soundcloud_album_id.isnot(None),
            )
            .group_by(ArtistCatalogRelease.artist_id)
            .subquery()
        )
        stmt = (
            select(Artist.id)
            .outerjoin(
                last_sync_sq,
                last_sync_sq.c.artist_id == Artist.id,
            )
            .where(
                Artist.soundcloud_user_id.isnot(None),
                or_(
                    last_sync_sq.c.last_sync.is_(None),
                    last_sync_sq.c.last_sync < cutoff,
                ),
            )
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [r for (r,) in rows.all()]

    async def count_artists_by_enrichment_status(
        self,
    ) -> dict[str, int]:
        """Return count of artists grouped by enrichment_status."""
        from app.models.artist import Artist

        cnt = func.count(Artist.id).label("cnt")
        stmt = select(Artist.enrichment_status, cnt).group_by(
            Artist.enrichment_status
        )
        rows = await self._session.execute(stmt)
        return {str(status): int(count) for status, count in rows.all()}

    async def apply_release_display_order(
        self,
        artist_id: int,
        ordered_release_ids: list[int],
    ) -> None:
        for pos, rid in enumerate(ordered_release_ids):
            rel = await self.get_release_for_artist(artist_id, rid)
            if rel is None:
                msg = f"unknown release id {rid}"
                raise ValueError(msg)
            rel.display_position = pos
        await self._session.flush()
