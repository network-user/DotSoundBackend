import structlog
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import TrackArtist
from app.models.track import Track
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackRepository(BaseRepository[Track]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Track)

    async def get_unique_genres(self) -> list[str]:
        result = await self._session.execute(
            select(Track.genre)
            .where(
                Track.genre.isnot(None),
                Track.genre != "",
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                self._exclude_hidden_sources(),
                self._playback_listing_allowed(),
            )
            .distinct()
            .order_by(Track.genre.asc())
        )
        return [str(g) for g in result.scalars().all() if g]

    async def get_total_uploaded_bytes(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(Track.file_size_bytes), 0)).where(
                Track.uploaded_by_id == user_id,
                Track.is_active.is_(True),
            )
        )
        return result.scalar_one()

    @staticmethod
    def _playable_filter():  # type: ignore[no-untyped-def]  # noqa: ANN205
        return Track.file_key.isnot(None) | (
            Track.access_mode.in_(
                (
                    "third_party_stream",
                    "official_embed",
                )
            )
        )

    @staticmethod
    def _exclude_hidden_sources():  # noqa: ANN205
        hidden = ("youtube",)
        source_platform = func.lower(
            func.coalesce(Track.source_platform, "")
        )
        imported_from = func.lower(
            func.coalesce(Track.imported_from, "")
        )
        return (~source_platform.in_(hidden)) & (
            ~imported_from.in_(hidden)
        )

    @staticmethod
    def _playback_listing_allowed():  # noqa: ANN205
        return or_(
            Track.playback_suppressed_until.is_(None),
            Track.playback_suppressed_until <= func.now(),
        )

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 20,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        logger.debug("db_list_tracks", offset=offset, limit=limit)
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
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

    async def list_by_artist_ids(
        self,
        artist_ids: list[int],
        offset: int = 0,
        limit: int = 20,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        if not artist_ids:
            return [], 0
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
            & Track.id.in_(
                select(TrackArtist.track_id).where(
                    TrackArtist.artist_id.in_(artist_ids)
                )
            )
        )
        if playable_only:
            condition = condition & self._playable_filter()
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = int(total_result.scalar_one())
        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def list_by_artist_track_ids(
        self,
        track_ids: list[int],
        offset: int = 0,
        limit: int = 20,
        public_only: bool = True,
    ) -> tuple[list[Track], int]:
        if not track_ids:
            return [], 0
        condition = Track.id.in_(track_ids) & (Track.is_active.is_(True))
        if public_only:
            condition = (
                condition
                & Track.is_public.is_(True)
                & self._exclude_hidden_sources()
                & self._playback_listing_allowed()
            )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = int(total_result.scalar_one())
        tracks_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc())
            .offset(offset)
            .limit(limit)
        )
        return (
            list(tracks_result.scalars().all()),
            total,
        )

    async def list_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        condition = (
            Track.is_active.is_(True)
            & self._exclude_hidden_sources()
            & (Track.uploaded_by_id == user_id)
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

    async def get_by_ids_preserve_order(
        self, track_ids: list[int]
    ) -> list[Track]:
        if not track_ids:
            return []
        result = await self._session.execute(
            select(Track).where(
                Track.id.in_(track_ids),
                self._exclude_hidden_sources(),
                self._playback_listing_allowed(),
            )
        )
        by_id = {t.id: t for t in result.scalars().all()}
        return [by_id[i] for i in track_ids if i in by_id]

    async def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
        playable_only: bool = False,
        genre_filter: str | None = None,
    ) -> tuple[list[Track], int]:
        q = query.strip()
        base = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
        )
        if genre_filter:
            genre_pattern = f"%{genre_filter.strip()}%"
            base = base & Track.genre.ilike(genre_pattern)
        elif q:
            pattern = f"%{q}%"
            base = base & (
                Track.title.ilike(pattern)
                | Track.artist.ilike(pattern)
                | Track.genre.ilike(pattern)
            )
        condition = (
            base & self._playable_filter()
            if playable_only
            else base
        )
        logger.debug(
            "db_search_tracks",
            query=query,
            genre_filter=genre_filter,
            offset=offset,
        )
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

    async def find_by_title_and_duration(
        self,
        title: str,
        duration_seconds: int,
        *,
        platform: str,
        tolerance_pct: float = 0.10,
        limit: int = 5,
    ) -> list[Track]:
        low = int(duration_seconds * (1.0 - tolerance_pct))
        high = int(duration_seconds * (1.0 + tolerance_pct))
        low = max(low, duration_seconds - 10)
        high = max(high, duration_seconds + 10)
        pattern = f"%{title}%"
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & self._playback_listing_allowed()
            & (Track.source_platform == platform)
            & Track.title.ilike(pattern)
            & Track.duration_seconds.between(low, high)
        )
        result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_by_similar_title(
        self,
        *,
        platform: str,
        title_queries: list[str],
        duration_seconds: int | None,
        duration_window_sec: int = 45,
        limit: int = 5,
    ) -> list[Track]:
        clean = [q.strip() for q in title_queries if q.strip()]
        if not clean:
            return []
        title_cond = or_(*[Track.title.ilike(f"%{q}%") for q in clean])
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & self._playback_listing_allowed()
            & (Track.source_platform == platform)
            & title_cond
        )
        if duration_seconds is not None:
            low = max(0, duration_seconds - duration_window_sec)
            high = duration_seconds + duration_window_sec
            condition = (
                condition
                & Track.duration_seconds.isnot(None)
                & Track.duration_seconds.between(low, high)
            )
            duration_diff = func.abs(
                Track.duration_seconds - duration_seconds
            )
        else:
            duration_diff = case(
                (Track.duration_seconds.is_(None), 999999),
                else_=0,
            )
        result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(duration_diff.asc(), Track.play_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
            logger.warning("db_play_count_track_missing", track_id=track_id)
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
    _ADMIN_PATCHABLE = _UPDATABLE_FIELDS | frozenset(
        {
            "sc_url",
            "source_url",
            "canonical_source_url",
        }
    )
    _ADMIN_NULLABLE_URL_FIELDS = frozenset(
        {
            "sc_url",
            "source_url",
            "canonical_source_url",
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
                Track.catalog_type == "ugc",
                Track.is_active.is_(True),
            )
            .values(**values)
            .returning(Track)
        )
        await self._session.flush()
        return result.scalar_one_or_none()

    async def admin_update_track(
        self,
        track_id: int,
        **fields: object,
    ) -> Track | None:
        values: dict[str, object] = {}
        for k, raw in fields.items():
            if k not in self._ADMIN_PATCHABLE:
                continue
            if raw is None:
                if k in self._ADMIN_NULLABLE_URL_FIELDS:
                    values[k] = None
                continue
            values[k] = raw
        if not values:
            return None
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.is_active.is_(True),
            )
            .values(**values)
            .returning(Track)
        )
        await self._session.flush()
        return result.scalar_one_or_none()

    async def get_track_id_by_sc_url(self, sc_url: str) -> int | None:
        result = await self._session.execute(
            select(Track.id).where(Track.sc_url == sc_url).limit(1)
        )
        return result.scalar_one_or_none()

    async def other_track_has_imported_external(
        self,
        *,
        imported_from: str,
        external_id: str,
        exclude_track_id: int,
    ) -> bool:
        result = await self._session.execute(
            select(Track.id)
            .where(
                Track.imported_from == imported_from,
                Track.external_id == external_id,
                Track.id != exclude_track_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def update_sc_url(
        self,
        track_id: int,
        sc_url: str,
        external_id: str | None = None,
    ) -> None:
        values: dict[str, object] = {"sc_url": sc_url}
        if external_id is not None:
            values["external_id"] = external_id
        await self._session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(**values)
        )
        await self._session.flush()

    async def get_active_by_uploader_and_blob_id(
        self,
        user_id: int,
        blob_id: int,
    ) -> Track | None:
        r = await self._session.execute(
            select(Track)
            .where(
                Track.uploaded_by_id == user_id,
                Track.blob_id == blob_id,
                Track.is_active.is_(True),
            )
            .limit(1)
        )
        return r.scalars().first()

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
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
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

        next_row = (await self._session.execute(next_q)).scalar_one_or_none()
        prev_row = (await self._session.execute(prev_q)).scalar_one_or_none()
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
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
            & (Track.id != track_id)
        )
        result = await self._session.execute(
            select(Track)
            .where(
                base
                & or_(
                    Track.created_at < ct,
                    (Track.created_at == ct) & (Track.id < tid),
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
                & self._exclude_hidden_sources()
                & self._playback_listing_allowed()
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
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
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
            & self._exclude_hidden_sources()
            & self._playback_listing_allowed()
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

    @staticmethod
    def _genre_sample_track_predicate():  # noqa: ANN205
        return (
            Track.blob_id.isnot(None)
            & Track.file_key.isnot(None)
            & Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & TrackRepository._exclude_hidden_sources()
            & TrackRepository._playback_listing_allowed()
            & Track.duration_seconds.isnot(None)
        )

    async def list_by_genre_for_genre_sample_backfill(
        self,
        genre: str,
        *,
        exclude_ids: set[int],
        limit: int,
    ) -> list[Track]:
        if limit <= 0:
            return []
        condition = (
            Track.genre == genre
        ) & self._genre_sample_track_predicate()
        if exclude_ids:
            condition = condition & Track.id.notin_(exclude_ids)
        result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc(), Track.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
