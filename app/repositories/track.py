from collections.abc import Collection
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.artist import TrackArtist
from app.models.track import Track
from app.models.user_track_library import UserTrackLibrary
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _result_rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


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
                self._playable_filter(),
            )
            .distinct()
            .order_by(Track.genre.asc())
        )
        return [str(g) for g in result.scalars().all() if g]

    async def get_total_uploaded_bytes(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(Track.file_size_bytes), 0)).where(
                Track.uploaded_by_id == user_id,
                Track.catalog_type == "ugc",
                Track.is_active.is_(True),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    def _playable_filter() -> ColumnElement[bool]:
        return Track.file_key.isnot(None) | (
            Track.access_mode.in_(
                (
                    "third_party_stream",
                    "official_embed",
                )
            )
        )

    @staticmethod
    def _exclude_hidden_sources() -> ColumnElement[bool]:
        hidden = ("youtube",)
        source_platform = func.lower(func.coalesce(Track.source_platform, ""))
        imported_from = func.lower(func.coalesce(Track.imported_from, ""))
        return (~source_platform.in_(hidden)) & (~imported_from.in_(hidden))

    @staticmethod
    def _playback_listing_allowed() -> ColumnElement[bool]:
        return Track.deleted_at.is_(None) & or_(
            Track.playback_suppressed_until.is_(None),
            Track.playback_suppressed_until <= func.now(),
        )

    async def get_access_info(
        self, track_id: int
    ) -> tuple[bool, int | None] | None:
        result = await self._session.execute(
            select(Track.is_public, Track.uploaded_by_id).where(
                Track.id == track_id,
                Track.deleted_at.is_(None),
            )
        )
        row = result.first()
        if row is None:
            return None
        owner_id = int(row[1]) if row[1] is not None else None
        return bool(row[0]), owner_id

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

    async def list_imported_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
        source_filter: str | None = None,
    ) -> tuple[list[Track], int]:
        source_expr = func.lower(
            func.coalesce(UserTrackLibrary.source, Track.imported_from, "")
        )
        condition = (
            Track.is_active.is_(True)
            & self._exclude_hidden_sources()
            & Track.deleted_at.is_(None)
            & (UserTrackLibrary.user_id == user_id)
            & (
                Track.imported_from.isnot(None)
                | (
                    UserTrackLibrary.source.isnot(None)
                    & (UserTrackLibrary.source != "upload")
                )
            )
        )
        if source_filter:
            condition = condition & (source_expr == source_filter.lower())
        total_result = await self._session.execute(
            select(func.count(Track.id))
            .select_from(Track)
            .join(
                UserTrackLibrary,
                UserTrackLibrary.track_id == Track.id,
            )
            .where(condition)
        )
        total = int(total_result.scalar_one())

        tracks_result = await self._session.execute(
            select(Track)
            .join(
                UserTrackLibrary,
                UserTrackLibrary.track_id == Track.id,
            )
            .where(condition)
            .order_by(UserTrackLibrary.imported_at.desc(), Track.id.desc())
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
            Track.is_active.is_(True)
            & self._exclude_hidden_sources()
            & (Track.uploaded_by_id == user_id)
            & (Track.catalog_type == "ugc")
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
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                self._exclude_hidden_sources(),
                self._playback_listing_allowed(),
            )
        )
        by_id = {t.id: t for t in result.scalars().all()}
        return [by_id[i] for i in track_ids if i in by_id]

    async def list_active_by_ids_preserve_order(
        self, track_ids: list[int]
    ) -> list[Track]:
        """Like :meth:`get_by_ids_preserve_order` but also drops
        soft-deleted rows. Used in user-facing recent/history feeds.
        """
        if not track_ids:
            return []
        result = await self._session.execute(
            select(Track).where(
                Track.id.in_(track_ids),
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                self._exclude_hidden_sources(),
            )
        )
        by_id = {t.id: t for t in result.scalars().all()}
        return [by_id[i] for i in track_ids if i in by_id]

    @staticmethod
    def _swipe_fill_predicate() -> ColumnElement[bool]:
        return (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & TrackRepository._playback_listing_allowed()
            & TrackRepository._playable_filter()
        )

    async def list_random_swipe_candidates(
        self,
        *,
        limit: int,
        genres: list[str] | None,
        exclude_ids: Collection[int],
        pool_size: int,
    ) -> list[Track]:
        """Randomized fill for the onboarding swipe candidate pool.

        Samples up to ``limit`` playable tracks out of the most-played
        ``pool_size`` rows matching the filters, so the ``random()``
        sort is bounded to that pool instead of ordering the whole
        catalogue by ``random()``.
        """
        if limit <= 0:
            return []
        condition = self._swipe_fill_predicate()
        if genres:
            condition = condition & Track.genre.in_(genres)
        if exclude_ids:
            condition = condition & Track.id.not_in(exclude_ids)
        pool = (
            select(Track.id)
            .where(condition)
            .order_by(Track.play_count.desc(), Track.id.desc())
            .limit(pool_size)
            .subquery()
        )
        result = await self._session.execute(
            select(Track)
            .join(pool, Track.id == pool.c.id)
            .order_by(func.random())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_top_played_swipe_candidates(
        self,
        *,
        limit: int,
        exclude_ids: Collection[int] | None = None,
    ) -> list[Track]:
        """Most-played playable tracks — the swipe pool fallback fill."""
        if limit <= 0:
            return []
        condition = self._swipe_fill_predicate()
        if exclude_ids:
            condition = condition & Track.id.not_in(exclude_ids)
        result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_internal_pending_hls(self) -> list[Track]:
        """Active internal-source tracks that still lack an HLS manifest."""
        result = await self._session.execute(
            select(Track).where(
                Track.source == "internal",
                Track.file_key.is_not(None),
                Track.hls_manifest_key.is_(None),
                Track.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def list_popular_genres(self, *, limit: int = 50) -> list[str]:
        """Top non-null genres ordered by track count (active public only)."""
        result = await self._session.execute(
            select(Track.genre)
            .where(
                Track.genre.is_not(None),
                Track.is_active.is_(True),
                Track.is_public.is_(True),
            )
            .group_by(Track.genre)
            .order_by(func.count(Track.id).desc())
            .limit(limit)
        )
        return [g for g in result.scalars().all() if g is not None]

    def _search_condition(
        self,
        query: str,
        *,
        playable_only: bool,
        genre_filter: str | None,
    ) -> ColumnElement[bool]:
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
        return base & self._playable_filter() if playable_only else base

    async def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
        playable_only: bool = False,
        genre_filter: str | None = None,
    ) -> tuple[list[Track], int]:
        condition = self._search_condition(
            query,
            playable_only=playable_only,
            genre_filter=genre_filter,
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
            .order_by(Track.play_count.desc(), Track.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(tracks_result.scalars().all()), total

    async def search_cursor(
        self,
        query: str,
        *,
        cursor_play_count: int | None,
        cursor_id: int | None,
        limit: int = 20,
        playable_only: bool = False,
        genre_filter: str | None = None,
    ) -> tuple[list[Track], int, bool]:
        """Keyset-paginate ``search`` on ``(play_count desc, id desc)``.

        Avoids the OFFSET cost of deep pagination; ``has_more`` tells
        the caller whether another page is available so the client can
        keep loading without re-counting.
        """
        condition = self._search_condition(
            query,
            playable_only=playable_only,
            genre_filter=genre_filter,
        )
        total = (
            await self._session.execute(
                select(func.count()).where(condition)
            )
        ).scalar_one()

        if cursor_play_count is not None and cursor_id is not None:
            condition = condition & or_(
                Track.play_count < cursor_play_count,
                and_(
                    Track.play_count == cursor_play_count,
                    Track.id < cursor_id,
                ),
            )
        rows_result = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.play_count.desc(), Track.id.desc())
            .limit(limit + 1)
        )
        rows = list(rows_result.scalars().all())
        return rows[:limit], int(total), len(rows) > limit

    async def find_variants_by_title_and_duration(
        self,
        title: str,
        duration_seconds: int,
        *,
        platforms: list[str],
        tolerance_pct: float = 0.10,
        limit: int = 50,
    ) -> list[Track]:
        if not platforms:
            return []
        low = int(duration_seconds * (1.0 - tolerance_pct))
        high = int(duration_seconds * (1.0 + tolerance_pct))
        low = max(low, duration_seconds - 10)
        high = max(high, duration_seconds + 10)
        pattern = f"%{title}%"
        condition = (
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & self._playback_listing_allowed()
            & Track.source_platform.in_(platforms)
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
            duration_diff: ColumnElement[int] = func.abs(
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
        updated = _result_rowcount(result) > 0
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
                Track.catalog_type == "ugc",
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
        values: dict[str, object] = {
            "sc_url": sc_url,
            "source_url": sc_url,
            "canonical_source_url": sc_url,
        }
        if external_id is not None:
            values["external_id"] = external_id
        await self._session.execute(
            update(Track).where(Track.id == track_id).values(**values)
        )
        await self._session.flush()

    async def list_soundcloud_playback_repair_candidates(
        self,
        *,
        limit: int,
    ) -> list[Track]:
        if limit <= 0:
            return []
        source_platform = func.lower(
            func.coalesce(Track.source_platform, "")
        )
        soundcloud = (source_platform == "soundcloud") | (
            Track.sc_url.isnot(None)
        )
        needs_repair = (
            Track.playback_last_failure_at.isnot(None)
            | Track.playback_recovery_failed_at.isnot(None)
            | (
                Track.playback_suppressed_until.isnot(None)
                & (Track.playback_suppressed_until > func.now())
            )
        )
        repair_rank = case((needs_repair, 0), else_=1)
        checked_rank = case(
            (Track.playback_last_checked_at.is_(None), 0),
            else_=1,
        )
        result = await self._session.execute(
            select(Track)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                Track.deleted_at.is_(None),
                Track.access_mode == "third_party_stream",
                soundcloud,
            )
            .order_by(
                repair_rank.asc(),
                Track.playback_last_failure_at.desc(),
                checked_rank.asc(),
                Track.playback_last_checked_at.asc(),
                Track.id.asc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_soundcloud_playback_audit_ids(
        self,
        *,
        limit: int,
        search: str | None = None,
        include_recently_checked: bool = False,
    ) -> list[int]:
        if limit <= 0:
            return []
        source_platform = func.lower(
            func.coalesce(Track.source_platform, "")
        )
        soundcloud = (source_platform == "soundcloud") | (
            Track.sc_url.isnot(None)
        )
        needs_attention = (
            Track.playback_last_checked_at.is_(None)
            | Track.playback_last_failure_at.isnot(None)
            | Track.playback_recovery_failed_at.isnot(None)
            | (
                Track.playback_suppressed_until.isnot(None)
                & (Track.playback_suppressed_until > func.now())
            )
        )
        query = select(Track.id).where(
            Track.is_active.is_(True),
            Track.is_public.is_(True),
            Track.deleted_at.is_(None),
            Track.access_mode == "third_party_stream",
            soundcloud,
        )
        if not include_recently_checked:
            query = query.where(needs_attention)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        needs_rank = case((needs_attention, 0), else_=1)
        checked_rank = case(
            (Track.playback_last_checked_at.is_(None), 0),
            else_=1,
        )
        result = await self._session.execute(
            query.order_by(
                needs_rank.asc(),
                Track.playback_last_failure_at.desc(),
                checked_rank.asc(),
                Track.playback_last_checked_at.asc(),
                Track.id.asc(),
            ).limit(limit)
        )
        return [int(track_id) for track_id in result.scalars().all()]

    async def find_existing_by_normalized_title_artist(
        self,
        pairs: list[tuple[str, str]],
        *,
        candidate_cap: int = 5000,
    ) -> dict[tuple[str, str], Track]:
        """Batched preflight lookup for the import pipeline.

        Given a list of normalized ``(title, artist)`` pairs, returns
        a mapping from each matched pair to the best existing Track
        (most-played wins on ties). Pairs without a hit are simply
        absent from the result dict — callers fall through to the
        external matcher.

        Normalization is the caller's responsibility (use
        :func:`app.utils.text_normalize.normalize_for_match`); the SQL
        side mirrors it via ``lower(trim(coalesce(...)))`` so an
        index on ``title`` is still usable as a prefilter.
        """
        if not pairs:
            return {}
        unique_titles: list[str] = []
        seen: set[str] = set()
        for title, _artist in pairs:
            if title and title not in seen:
                seen.add(title)
                unique_titles.append(title)
        if not unique_titles:
            return {}
        norm_title = func.lower(func.trim(Track.title))
        result = await self._session.execute(
            select(Track)
            .where(
                norm_title.in_(unique_titles),
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                self._exclude_hidden_sources(),
                self._playback_listing_allowed(),
                self._playable_filter(),
            )
            .order_by(Track.play_count.desc())
            .limit(candidate_cap)
        )
        candidates = list(result.scalars().all())
        wanted: set[tuple[str, str]] = {(t, a) for t, a in pairs if t}
        out: dict[tuple[str, str], Track] = {}
        for track in candidates:
            t_norm = (track.title or "").strip().lower()
            a_norm = (track.artist or "").strip().lower()
            key = (t_norm, a_norm)
            if key in wanted and key not in out:
                out[key] = track
        return out

    async def get_active_by_uploader_and_blob_id(
        self,
        user_id: int,
        blob_id: int,
    ) -> Track | None:
        r = await self._session.execute(
            select(Track)
            .where(
                Track.uploaded_by_id == user_id,
                Track.catalog_type == "ugc",
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
        if track.catalog_type != "ugc":
            return None
        if track.deleted_at is not None:
            return None
        track.is_active = False
        track.deleted_at = datetime.now(UTC)
        track.deleted_by_id = user_id
        track.deleted_reason = "owner"
        await self._session.flush()
        return track

    async def restore_by_owner(
        self, track_id: int, user_id: int
    ) -> Track | None:
        track = await self.get_by_id(track_id)
        if not track or track.uploaded_by_id != user_id:
            return None
        if track.catalog_type != "ugc":
            return None
        if track.deleted_at is None:
            return None
        if track.deleted_reason not in ("owner", None):
            return None
        track.is_active = True
        track.deleted_at = None
        track.deleted_by_id = None
        track.deleted_reason = None
        await self._session.flush()
        return track

    async def admin_soft_delete(
        self,
        track_id: int,
        *,
        by_user_id: int,
        reason: str,
    ) -> Track | None:
        track = await self.get_by_id(track_id)
        if not track:
            return None
        if track.deleted_at is not None:
            return track
        track.is_active = False
        track.deleted_at = datetime.now(UTC)
        track.deleted_by_id = by_user_id
        track.deleted_reason = reason
        await self._session.flush()
        return track

    async def admin_restore(self, track_id: int) -> Track | None:
        track = await self.get_by_id(track_id)
        if not track or track.deleted_at is None:
            return None
        track.is_active = True
        track.deleted_at = None
        track.deleted_by_id = None
        track.deleted_reason = None
        await self._session.flush()
        return track

    async def list_user_trash(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Track], int]:
        condition = (
            (Track.uploaded_by_id == user_id)
            & (Track.catalog_type == "ugc")
            & Track.deleted_at.is_not(None)
            & (Track.deleted_reason == "owner")
        )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = int(total_result.scalar_one())
        rows = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.deleted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total

    async def list_admin_deleted(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        condition: ColumnElement[bool] = Track.deleted_at.is_not(None)
        if search:
            pattern = f"%{search.strip()}%"
            condition = condition & (
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        total = int(total_result.scalar_one())
        rows = await self._session.execute(
            select(Track)
            .where(condition)
            .order_by(Track.deleted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total

    async def list_admin_deleted_ids(
        self,
        *,
        search: str | None = None,
    ) -> tuple[list[int], int]:
        condition: ColumnElement[bool] = Track.deleted_at.is_not(None)
        if search:
            pattern = f"%{search.strip()}%"
            condition = condition & (
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        total_result = await self._session.execute(
            select(func.count()).where(condition)
        )
        rows = await self._session.execute(
            select(Track.id).where(condition).order_by(Track.deleted_at.desc())
        )
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total_result.scalar_one()
        )

    async def list_hard_delete_candidates(
        self,
        *,
        limit: int = 50,
    ) -> list[Track]:
        rows = await self._session.execute(
            select(Track)
            .where(Track.deleted_at.is_not(None))
            .order_by(Track.deleted_at.asc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def hard_delete_track(self, track_id: int) -> bool:
        result = await self._session.execute(
            delete(Track).where(Track.id == track_id)
        )
        await self._session.flush()
        return _result_rowcount(result) > 0

    async def get_for_owner_including_trash(
        self, track_id: int, user_id: int
    ) -> Track | None:
        track = await self.get_by_id(track_id)
        if (
            not track
            or track.uploaded_by_id != user_id
            or track.catalog_type != "ugc"
        ):
            return None
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
            & (Track.access_mode != "external_link")
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
            & (Track.catalog_type == "ugc")
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
            & (Track.catalog_type == "ugc")
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
    def _genre_sample_track_predicate() -> ColumnElement[bool]:
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

    async def list_covers_above_id(
        self,
        cursor: int,
        limit: int,
    ) -> list[tuple[int, str, datetime | None]]:
        if limit <= 0:
            return []
        result = await self._session.execute(
            select(Track.id, Track.cover_key, Track.updated_at)
            .where(
                Track.id > cursor,
                Track.cover_key.isnot(None),
                Track.cover_key != "",
                Track.deleted_at.is_(None),
            )
            .order_by(Track.id.asc())
            .limit(limit)
        )
        return [(int(r[0]), str(r[1]), r[2]) for r in result.all()]

    async def swap_cover_key_if_unchanged(
        self,
        track_id: int,
        old_cover_key: str,
        new_cover_key: str,
    ) -> bool:
        result = await self._session.execute(
            update(Track)
            .where(
                Track.id == track_id,
                Track.cover_key == old_cover_key,
                Track.deleted_at.is_(None),
            )
            .values(cover_key=new_cover_key)
        )
        return _result_rowcount(result) > 0
