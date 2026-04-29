import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class ArtistRepository(BaseRepository[Artist]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Artist)

    async def find_by_normalized_name(
        self, name_normalized: str
    ) -> Artist | None:
        result = await self._session.execute(
            select(Artist)
            .where(Artist.name_normalized == name_normalized)
            .order_by(Artist.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_by_soundcloud_user_id(
        self,
        soundcloud_user_id: int,
        *,
        exclude_artist_id: int | None = None,
    ) -> Artist | None:
        q = (
            select(Artist)
            .where(Artist.soundcloud_user_id == soundcloud_user_id)
            .order_by(Artist.id.asc())
            .limit(1)
        )
        if exclude_artist_id is not None:
            q = q.where(Artist.id != exclude_artist_id)
        result = await self._session.execute(q)
        return result.scalar_one_or_none()

    async def get_by_ids_preserve_order(
        self, artist_ids: list[int]
    ) -> list[Artist]:
        if not artist_ids:
            return []
        result = await self._session.execute(
            select(Artist).where(Artist.id.in_(artist_ids))
        )
        by_id = {a.id: a for a in result.scalars().all()}
        return [by_id[i] for i in artist_ids if i in by_id]

    async def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Artist]:
        pattern = f"%{query.lower()}%"
        result = await self._session.execute(
            select(Artist)
            .where(
                or_(
                    Artist.name_normalized.ilike(pattern),
                    Artist.soundcloud_permalink.ilike(pattern),
                )
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_popular(
        self,
        limit: int = 50,
        genre_filter: list[str] | None = None,
    ) -> list[Artist]:
        q = (
            select(
                Artist,
                func.count(TrackArtist.track_id).label("track_count"),
            )
            .join(
                TrackArtist,
                TrackArtist.artist_id == Artist.id,
            )
            .group_by(Artist.id)
            .order_by(func.count(TrackArtist.track_id).desc())
            .limit(limit)
        )
        result = await self._session.execute(q)
        return [row[0] for row in result.all()]

    async def link_track(
        self,
        track_id: int,
        artist_id: int,
        role: str = "primary",
        position: int = 0,
    ) -> None:
        bind = self._session.get_bind()
        dialect = bind.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import (
                insert as insert_pg,
            )

            await self._session.execute(
                insert_pg(TrackArtist)
                .values(
                    track_id=track_id,
                    artist_id=artist_id,
                    role=role,
                    position=position,
                )
                .on_conflict_do_nothing(constraint="uq_track_artist")
            )
            return
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import (
                insert as insert_sqlite,
            )

            await self._session.execute(
                insert_sqlite(TrackArtist)
                .values(
                    track_id=track_id,
                    artist_id=artist_id,
                    role=role,
                    position=position,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "track_id",
                        "artist_id",
                    ],
                )
            )
            return
        existing = await self._session.execute(
            select(TrackArtist).where(
                TrackArtist.track_id == track_id,
                TrackArtist.artist_id == artist_id,
            )
        )
        if existing.scalar_one_or_none():
            return
        link = TrackArtist(
            track_id=track_id,
            artist_id=artist_id,
            role=role,
            position=position,
        )
        self._session.add(link)
        await self._session.flush()

    async def get_track_artists(self, track_id: int) -> list[Artist]:
        result = await self._session.execute(
            select(Artist)
            .join(
                TrackArtist,
                TrackArtist.artist_id == Artist.id,
            )
            .where(TrackArtist.track_id == track_id)
            .order_by(TrackArtist.position)
        )
        return list(result.scalars().all())

    async def get_artist_track_ids(
        self,
        artist_id: int,
        limit: int = 100,
    ) -> list[int]:
        result = await self._session.execute(
            select(TrackArtist.track_id)
            .where(TrackArtist.artist_id == artist_id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_soundcloud_identity(
        self,
        artist_id: int,
        *,
        soundcloud_user_id: int | None,
        soundcloud_permalink: str | None,
    ) -> Artist | None:
        artist = await self.get_by_id(artist_id)
        if artist is None:
            return None
        artist.soundcloud_user_id = soundcloud_user_id
        artist.soundcloud_permalink = soundcloud_permalink
        await self._session.flush()
        return artist
