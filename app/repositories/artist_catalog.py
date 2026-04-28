from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track
from app.repositories.base import BaseRepository


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
