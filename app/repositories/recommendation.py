import structlog
from dotsound_private_core.services.recommendation_language_policy import (
    RUS_CANDIDATE_CYRILLIC_PATTERN,
    cyrillic_likely_ru_title_artist,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import TrackArtist
from app.models.like import Like
from app.models.listen_event import ListenEvent
from app.models.track import Track

logger = structlog.get_logger(__name__)


class RecommendationRepository:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._session = session

    async def get_candidate_tracks(
        self,
        limit: int = 200,
        genre_filter: list[str] | None = None,
        exclude_ids: set[int] | None = None,
    ) -> list[Track]:
        q = select(Track).where(
            Track.is_active.is_(True),
            Track.is_public.is_(True),
        )
        if genre_filter:
            q = q.where(
                Track.genre.in_(genre_filter)
            )
        if exclude_ids:
            q = q.where(
                Track.id.notin_(exclude_ids)
            )
        q = q.order_by(
            Track.play_count.desc()
        ).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get_cyrillic_likely_ru_candidates(
        self,
        limit: int = 100,
        genre_filter: list[str] | None = None,
        exclude_ids: set[int] | None = None,
    ) -> list[Track]:
        q = select(Track).where(
            Track.is_active.is_(True),
            Track.is_public.is_(True),
        )
        if genre_filter:
            q = q.where(
                Track.genre.in_(genre_filter)
            )
        if exclude_ids:
            q = q.where(
                Track.id.notin_(exclude_ids)
            )
        bind = self._session.get_bind()
        dialect = bind.dialect.name
        if dialect == "postgresql":
            pat = RUS_CANDIDATE_CYRILLIC_PATTERN
            q = q.where(
                or_(
                    func.coalesce(Track.title, "").op("~")(
                        pat
                    ),
                    func.coalesce(Track.artist, "").op("~")(
                        pat
                    ),
                )
            )
            q = q.order_by(
                Track.play_count.desc()
            ).limit(limit)
        else:
            cap = min(2000, max(limit * 30, 300))
            q = q.order_by(
                Track.play_count.desc()
            ).limit(cap)
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        if dialect != "postgresql":
            rows = [
                t
                for t in rows
                if cyrillic_likely_ru_title_artist(
                    t.title, t.artist
                )
            ][:limit]
        return rows

    async def get_candidate_tracks_stratified(
        self,
        total_limit: int = 200,
        genre_filter: list[str] | None = None,
        exclude_ids: set[int] | None = None,
        cyrillic_strata_ratio: float = 0.4,
    ) -> list[Track]:
        n_cyr = int(total_limit * cyrillic_strata_ratio)
        n_glob = max(0, total_limit - n_cyr)
        ex0 = set(exclude_ids) if exclude_ids else set()
        global_tracks: list[Track] = []
        if n_glob > 0:
            global_tracks = await self.get_candidate_tracks(
                limit=n_glob,
                genre_filter=genre_filter,
                exclude_ids=ex0,
            )
        gids = {t.id for t in global_tracks}
        cyr_tracks: list[Track] = []
        if n_cyr > 0:
            cyr_tracks = await self.get_cyrillic_likely_ru_candidates(
                limit=n_cyr,
                genre_filter=genre_filter,
                exclude_ids=ex0 | gids,
            )
        seen: set[int] = set()
        out: list[Track] = []
        for t in global_tracks + cyr_tracks:
            if t.id in seen:
                continue
            seen.add(t.id)
            out.append(t)
        if len(out) < total_limit:
            need = total_limit - len(out)
            more = await self.get_candidate_tracks(
                limit=need + len(seen) + 50,
                genre_filter=genre_filter,
                exclude_ids=seen | ex0,
            )
            for t in more:
                if t.id in seen:
                    continue
                seen.add(t.id)
                out.append(t)
                if len(out) >= total_limit:
                    break
        return out[:total_limit]

    async def get_popular_tracks(
        self, limit: int = 20
    ) -> list[Track]:
        result = await self._session.execute(
            select(Track)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
            )
            .order_by(Track.play_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_tracks(
        self,
        days: int = 7,
        limit: int = 20,
    ) -> list[Track]:
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(
            days=days
        )
        result = await self._session.execute(
            select(Track)
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                Track.created_at >= cutoff,
            )
            .order_by(Track.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_tracks_by_artist_ids(
        self,
        artist_ids: list[int],
        limit: int = 20,
    ) -> list[Track]:
        if not artist_ids:
            return []
        result = await self._session.execute(
            select(Track)
            .join(
                TrackArtist,
                TrackArtist.track_id == Track.id,
            )
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                TrackArtist.artist_id.in_(
                    artist_ids
                ),
            )
            .order_by(Track.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_liked_track_ids(
        self, user_id: int
    ) -> set[int]:
        result = await self._session.execute(
            select(Like.track_id).where(
                Like.user_id == user_id
            )
        )
        return set(result.scalars().all())

    async def get_listened_track_ids(
        self, user_id: int
    ) -> set[int]:
        result = await self._session.execute(
            select(ListenEvent.track_id)
            .where(ListenEvent.user_id == user_id)
            .distinct()
        )
        return set(result.scalars().all())

    async def get_incomplete_listens(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[Track]:
        subq = (
            select(
                ListenEvent.track_id,
                func.max(
                    ListenEvent.created_at
                ).label("last_listen"),
            )
            .where(
                ListenEvent.user_id == user_id,
                ListenEvent.completed.is_(False),
                ListenEvent.skipped.is_(False),
            )
            .group_by(ListenEvent.track_id)
            .order_by(
                func.max(
                    ListenEvent.created_at
                ).desc()
            )
            .limit(limit)
            .subquery()
        )
        result = await self._session.execute(
            select(Track)
            .join(
                subq, subq.c.track_id == Track.id
            )
            .where(Track.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_tracks_by_ids(
        self, ids: list[int]
    ) -> list[Track]:
        if not ids:
            return []
        result = await self._session.execute(
            select(Track).where(Track.id.in_(ids))
        )
        id_order = {
            tid: i for i, tid in enumerate(ids)
        }
        tracks = list(result.scalars().all())
        tracks.sort(
            key=lambda t: id_order.get(t.id, 9999)
        )
        return tracks

    async def get_track_artist_map(
        self, track_ids: list[int]
    ) -> dict[int, list[int]]:
        if not track_ids:
            return {}
        result = await self._session.execute(
            select(
                TrackArtist.track_id,
                TrackArtist.artist_id,
            ).where(
                TrackArtist.track_id.in_(track_ids)
            )
        )
        mapping: dict[int, list[int]] = {}
        for row in result.all():
            mapping.setdefault(
                row[0], []
            ).append(row[1])
        return mapping
