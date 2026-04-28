from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
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
