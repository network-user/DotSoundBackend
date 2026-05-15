import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.models.artist_similarity import ArtistSimilarity
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

    async def find_by_owner_user_id(
        self,
        owner_user_id: int,
    ) -> Artist | None:
        result = await self._session.execute(
            select(Artist)
            .where(Artist.owner_user_id == owner_user_id)
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

    async def list_admin(
        self,
        *,
        q: str | None,
        q_normalized: str | None,
        enrichment_filter: str | None,
        page: int,
        size: int,
    ) -> tuple[list[Artist], int]:
        stmt = select(Artist)
        count_stmt = select(func.count(Artist.id))
        predicates = []
        if q_normalized:
            pattern = f"%{q_normalized.lower()}%"
            predicates.append(Artist.name_normalized.ilike(pattern))
        if q:
            raw_pattern = f"%{q.lower()}%"
            predicates.append(Artist.name_normalized.ilike(raw_pattern))
            predicates.append(Artist.soundcloud_permalink.ilike(raw_pattern))
        if predicates:
            predicate = or_(*predicates)
            stmt = stmt.where(predicate)
            count_stmt = count_stmt.where(predicate)
        if enrichment_filter:
            if enrichment_filter == "needs_data":
                stmt = stmt.where(
                    Artist.enrichment_status.in_(
                        ("pending", "not_found", "failed")
                    )
                )
                count_stmt = count_stmt.where(
                    Artist.enrichment_status.in_(
                        ("pending", "not_found", "failed")
                    )
                )
            else:
                stmt = stmt.where(
                    Artist.enrichment_status == enrichment_filter
                )
                count_stmt = count_stmt.where(
                    Artist.enrichment_status == enrichment_filter
                )
        stmt = (
            stmt.order_by(Artist.updated_at.desc(), Artist.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = await self._session.execute(stmt)
        total = await self._session.scalar(count_stmt)
        return list(rows.scalars().all()), int(total or 0)

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

    async def get_track_artists_with_roles(
        self, track_id: int
    ) -> list[tuple[Artist, str, int]]:
        result = await self._session.execute(
            select(Artist, TrackArtist.role, TrackArtist.position)
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id == track_id)
            .order_by(TrackArtist.position)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_tracks_artists_with_roles_batch(
        self, track_ids: list[int]
    ) -> dict[int, list[tuple[Artist, str, int]]]:
        if not track_ids:
            return {}
        result = await self._session.execute(
            select(
                Artist,
                TrackArtist.role,
                TrackArtist.position,
                TrackArtist.track_id,
            )
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id.in_(track_ids))
            .order_by(TrackArtist.track_id, TrackArtist.position)
        )
        out: dict[int, list[tuple[Artist, str, int]]] = {}
        for artist, role, position, track_id in result.all():
            out.setdefault(track_id, []).append((artist, role, position))
        return out

    async def get_all_artist_track_ids(
        self,
        artist_id: int,
        limit: int = 500,
    ) -> list[int]:
        """All track ids where artist has any credit (primary or featured)."""
        result = await self._session.execute(
            select(TrackArtist.track_id)
            .where(TrackArtist.artist_id == artist_id)
            .order_by(TrackArtist.track_id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_similar_artists_from_similarity_index(
        self,
        artist_id: int,
        *,
        limit: int,
    ) -> list[tuple[int, float]]:
        stmt = (
            select(
                ArtistSimilarity.similar_artist_id,
                func.max(ArtistSimilarity.score),
            )
            .where(ArtistSimilarity.artist_id == artist_id)
            .group_by(ArtistSimilarity.similar_artist_id)
            .order_by(func.max(ArtistSimilarity.score).desc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        out: list[tuple[int, float]] = []
        for sid, raw in rows.all():
            if sid is None or raw is None:
                continue
            out.append((int(sid), float(raw)))
        return out

    async def get_artist_track_ids(
        self,
        artist_id: int,
        limit: int = 100,
    ) -> list[int]:
        """Track ids where this artist shares top billing (min position).

        Excludes tracks where the artist is only a featured credit
        (higher position than another artist on the same track).
        """
        min_pos = (
            select(
                TrackArtist.track_id.label("tid"),
                func.min(TrackArtist.position).label("mp"),
            )
            .group_by(TrackArtist.track_id)
            .subquery()
        )
        stmt = (
            select(TrackArtist.track_id)
            .join(
                min_pos,
                (TrackArtist.track_id == min_pos.c.tid)
                & (TrackArtist.position == min_pos.c.mp),
            )
            .where(TrackArtist.artist_id == artist_id)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
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
