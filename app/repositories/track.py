import structlog
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackRepository(BaseRepository[Track]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Track)

    async def get_unique_genres(self) -> list[str]:
        result = await self._session.execute(
            select(Track.genre)
            .where(Track.genre.isnot(None), Track.genre != "")
            .distinct()
            .order_by(Track.genre.asc())
        )
        return [str(g) for g in result.scalars().all() if g]

    async def get_total_uploaded_bytes(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(Track.file_size_bytes), 0))
            .where(
                Track.uploaded_by_id == user_id,
                Track.is_active.is_(True),
            )
        )
        return result.scalar_one()

    @staticmethod
    def _playable_filter():  # type: ignore[no-untyped-def]
        return (
            Track.file_key.isnot(None)
            | (
                Track.access_mode.in_(
                    (
                        "third_party_stream",
                        "official_embed",
                    )
                )
            )
        )

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 20,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        logger.debug("db_list_tracks", offset=offset, limit=limit)
        condition = Track.is_active.is_(True) & Track.is_public.is_(True)
        if playable_only:
            condition = condition & self._playable_filter()
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def list_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        condition = (
            Track.is_active.is_(True) & (Track.uploaded_by_id == user_id)
        )
        if playable_only:
            condition = condition & self._playable_filter()
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Track], int]:
        pattern = f"%{query}%"
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & (
                Track.title.ilike(pattern)
                | Track.artist.ilike(pattern)
            )
        )
        logger.debug("db_search_tracks", query=query, offset=offset)
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def increment_play_count(self, track_id: int) -> bool:
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.is_active.is_(True),
            )
            .values(play_count=Track.play_count + 1)
        )
        updated = result.rowcount > 0
        if updated:
            logger.debug("db_play_count_incremented", track_id=track_id)
        else:
            logger.warning(
                "db_play_count_track_missing", track_id=track_id
            )
        return updated

    async def update_visibility(
        self, track_id: int, user_id: int, is_public: bool
    ) -> Track | None:
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.uploaded_by_id == user_id,
                Track.is_active.is_(True),
            )
            .values(is_public=is_public)
            .returning(Track)
        )
        await self._session.flush()
        return result.scalar_one_or_none()

    _UPDATABLE_FIELDS = frozenset(
        {
            "title",
            "artist",
            "genre",
            "description",
            "is_public",
        }
    )

    async def update_track(
        self,
        track_id: int,
        user_id: int,
        **fields: object,
    ) -> Track | None:
        values = {
            k: v
            for k, v in fields.items()
            if k in self._UPDATABLE_FIELDS and v is not None
        }
        if not values:
            return None
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.uploaded_by_id == user_id,
                Track.is_active.is_(True),
            )
            .values(**values)
            .returning(Track)
        )
        await self._session.flush()
        return result.scalar_one_or_none()

    async def delete_by_owner(
        self, track_id: int, user_id: int
    ) -> Track | None:
        track = await self.get_by_id(track_id)
        if not track or track.uploaded_by_id != user_id:
            return None
        track.is_active = False
        await self._session.flush()
        return track

    async def get_adjacent(
        self, track_id: int
    ) -> tuple[int | None, int | None]:
        """Return (prev_id, next_id) based on created_at DESC ordering.

        prev_id = newer track (higher created_at / id).
        next_id = older track (lower created_at / id).
        Uses id as tiebreaker for identical created_at values.
        """
        track = await self.get_by_id(track_id)
        if not track:
            return None, None

        ct = track.created_at
        tid = track.id
        base = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & (Track.id != track_id)
        )

        next_q = (
            select(Track.id)
            .where(
                base
                & or_(
                    Track.created_at < ct,
                    (Track.created_at == ct) & (Track.id < tid),
                )
            )
            .order_by(Track.created_at.desc(), Track.id.desc())
            .limit(1)
        )
        prev_q = (
            select(Track.id)
            .where(
                base
                & or_(
                    Track.created_at > ct,
                    (Track.created_at == ct) & (Track.id > tid),
                )
            )
            .order_by(Track.created_at.asc(), Track.id.asc())
            .limit(1)
        )

        next_row = (
            await self._session.execute(next_q)
        ).scalar_one_or_none()
        prev_row = (
            await self._session.execute(prev_q)
        ).scalar_one_or_none()
        return prev_row, next_row

    async def get_next_tracks(
        self, track_id: int, count: int = 3
    ) -> list[Track]:
        track = await self.get_by_id(track_id)
        if not track:
            return []
        ct = track.created_at
        tid = track.id
        base = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & (Track.id != track_id)
        )
        result = await self._session.execute(
            select(Track)
            .where(
                base
                & or_(
                    Track.created_at < ct,
                    (Track.created_at == ct)
                    & (Track.id < tid),
                )
            )
            .order_by(
                Track.created_at.desc(),
                Track.id.desc(),
            )
            .limit(count)
        )
        return list(result.scalars().all())

    async def get_random_id(self, exclude_id: int) -> int | None:
        """Return a random active public track id, excluding exclude_id."""
        result = await self._session.execute(
            select(Track.id)
            .where(
                Track.is_active.is_(True)
                & Track.is_public.is_(True)
                & (Track.id != exclude_id)
            )
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_public_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Track], int]:
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & (Track.uploaded_by_id == user_id)
        )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def list_by_users_public(
        self,
        user_ids: list[int],
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Track], int]:
        if not user_ids:
            return [], 0
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & Track.uploaded_by_id.in_(user_ids)
        )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = total_result.scalar_one()

        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total
