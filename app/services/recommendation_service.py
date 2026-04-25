import json
from datetime import UTC, datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.track import Track
from app.repositories.preference import (
    PreferenceRepository,
)
from app.repositories.recommendation import (
    RecommendationRepository,
)
from app.repositories.signal import (
    ListenEventRepository,
)
from app.schemas.track import TrackResponse
from dotsound_private_core.services.recommendation_engine import (
    ListenEvent as RecListenEvent,
    ScoredTrack,
    TrackFeatures,
    UserPrefs,
    build_daily_mix,
    build_radio_queue,
    build_weekly_mix,
    merge_hybrid_playlist,
    score_tracks_for_user,
    select_similar_tracks,
)
from dotsound_private_core.services.scoring import (
    determine_maturity,
)

_DAILY_SIZE = 30
_WEEKLY_SIZE = 50
_EXTERNAL_RATIO = 0.3
_GLOBAL_TOP_SIZE = 20


def _midnight_ttl() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


def _weekly_ttl() -> int:
    now = datetime.now(timezone.utc)
    days_ahead = (7 - now.weekday()) % 7 or 7
    next_monday = (
        now + timedelta(days=days_ahead)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((next_monday - now).total_seconds()))

logger = structlog.get_logger(__name__)


class RecommendationService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._rec_repo = RecommendationRepository(
            session
        )
        self._pref_repo = PreferenceRepository(
            session
        )
        self._listen_repo = ListenEventRepository(
            session
        )
        self._session = session

    async def _build_user_prefs(
        self, user_id: int
    ) -> UserPrefs:
        pref = await self._pref_repo.get_by_user_id(
            user_id
        )
        liked_ids = (
            await self._rec_repo.get_liked_track_ids(
                user_id
            )
        )

        from app.models.dislike import Dislike
        from sqlalchemy import select

        dislike_result = (
            await self._session.execute(
                select(Dislike.track_id).where(
                    Dislike.user_id == user_id
                )
            )
        )
        disliked_ids = set(
            dislike_result.scalars().all()
        )

        return UserPrefs(
            preferred_genres=(
                pref.preferred_genres or []
                if pref
                else []
            ),
            preferred_artist_ids=(
                pref.preferred_artist_ids or []
                if pref
                else []
            ),
            preferred_moods=(
                pref.preferred_moods or []
                if pref
                else []
            ),
            liked_track_ids=liked_ids,
            disliked_track_ids=disliked_ids,
        )

    async def _build_listen_history(
        self, user_id: int
    ) -> list[RecListenEvent]:
        events = (
            await self._listen_repo.get_recent(
                user_id, limit=200
            )
        )
        return [
            RecListenEvent(
                track_id=e.track_id,
                completed=e.completed,
                skipped=e.skipped,
                created_at=e.created_at,
            )
            for e in events
        ]

    async def _tracks_to_features(
        self, tracks: list[Track]
    ) -> list[TrackFeatures]:
        track_ids = [t.id for t in tracks]
        artist_map = (
            await self._rec_repo.get_track_artist_map(
                track_ids
            )
        )
        return [
            TrackFeatures(
                track_id=t.id,
                genre=t.genre,
                artist_ids=artist_map.get(
                    t.id, []
                ),
                play_count=t.play_count,
                created_at=t.created_at,
                source=t.source,
            )
            for t in tracks
        ]

    async def get_home_sections(
        self, user_id: int
    ) -> dict:
        pref = await self._pref_repo.get_by_user_id(
            user_id
        )
        listen_count = (
            await self._listen_repo.count_for_user(
                user_id
            )
        )

        maturity = determine_maturity(
            onboarding_completed=(
                bool(pref and pref.onboarding_completed)
            ),
            calibration_completed=(
                bool(
                    pref
                    and pref.calibration_completed
                )
            ),
            enrichment_done=False,
            listen_count=listen_count,
        )

        sections: list[dict] = []

        continue_tracks = (
            await self._rec_repo.get_incomplete_listens(
                user_id, limit=10
            )
        )
        if continue_tracks:
            sections.append(
                {
                    "title": "Продолжить слушать",
                    "section_type": "continue",
                    "tracks": continue_tracks,
                }
            )

        user_prefs = await self._build_user_prefs(
            user_id
        )
        history = (
            await self._build_listen_history(
                user_id
            )
        )

        genre_filter = (
            pref.preferred_genres
            if pref and pref.preferred_genres
            else None
        )
        candidates = (
            await self._rec_repo.get_candidate_tracks(
                limit=200,
                genre_filter=genre_filter,
            )
        )

        if candidates:
            features = (
                await self._tracks_to_features(
                    candidates
                )
            )
            scored = score_tracks_for_user(
                user_prefs, history, features
            )
            scored_ids = [
                s.track_id for s in scored[:20]
            ]
            track_map = {
                t.id: t for t in candidates
            }
            for_you = [
                track_map[tid]
                for tid in scored_ids
                if tid in track_map
            ]
            if for_you:
                sections.append(
                    {
                        "title": "Для вас",
                        "section_type": (
                            "personalized"
                        ),
                        "tracks": for_you,
                    }
                )

        if genre_filter:
            popular_genre = (
                await self._rec_repo.get_candidate_tracks(
                    limit=15,
                    genre_filter=genre_filter,
                )
            )
            if popular_genre:
                title = (
                    f"Популярное: "
                    f"{genre_filter[0]}"
                )
                sections.append(
                    {
                        "title": title,
                        "section_type": (
                            "genre_popular"
                        ),
                        "tracks": popular_genre,
                    }
                )

        recent = (
            await self._rec_repo.get_recent_tracks(
                days=7, limit=15
            )
        )
        if recent:
            sections.append(
                {
                    "title": "Новые релизы",
                    "section_type": "new_releases",
                    "tracks": recent,
                }
            )

        if (
            pref
            and pref.preferred_artist_ids
        ):
            artist_tracks = (
                await self._rec_repo.get_tracks_by_artist_ids(
                    pref.preferred_artist_ids,
                    limit=15,
                )
            )
            if artist_tracks:
                sections.append(
                    {
                        "title": (
                            "Любимые исполнители"
                        ),
                        "section_type": (
                            "fav_artists"
                        ),
                        "tracks": artist_tracks,
                    }
                )

        if not sections:
            popular = (
                await self._rec_repo.get_popular_tracks(
                    limit=50
                )
            )
            sections.append(
                {
                    "title": "Популярное",
                    "section_type": "popular",
                    "tracks": popular,
                }
            )

        return {
            "sections": sections,
            "maturity": maturity,
        }

    async def get_similar(
        self, track_id: int, limit: int = 10
    ) -> list[Track]:
        from app.repositories.track import (
            TrackRepository,
        )

        track_repo = TrackRepository(self._session)
        seed = await track_repo.get_by_id(track_id)
        if not seed:
            return []

        candidates = (
            await self._rec_repo.get_candidate_tracks(
                limit=100,
                genre_filter=(
                    [seed.genre]
                    if seed.genre
                    else None
                ),
            )
        )
        if not candidates:
            return []

        all_tracks = [seed] + candidates
        features = await self._tracks_to_features(
            all_tracks
        )
        seed_feat = features[0]
        candidate_feats = features[1:]

        scored = select_similar_tracks(
            seed_feat, candidate_feats, limit=limit
        )
        track_map = {t.id: t for t in candidates}
        return [
            track_map[s.track_id]
            for s in scored
            if s.track_id in track_map
        ]

    async def get_daily_mix(
        self, user_id: int, size: int = 30
    ) -> list[Track]:
        user_prefs = await self._build_user_prefs(
            user_id
        )
        history = (
            await self._build_listen_history(
                user_id
            )
        )

        candidates = (
            await self._rec_repo.get_candidate_tracks(
                limit=200
            )
        )
        if not candidates:
            return []

        features = await self._tracks_to_features(
            candidates
        )
        scored = build_daily_mix(
            user_prefs, history, features, size
        )

        track_map = {t.id: t for t in candidates}
        return [
            track_map[s.track_id]
            for s in scored
            if s.track_id in track_map
        ]

    async def get_radio(
        self,
        seed_track_id: int,
        queue_size: int = 20,
        user_id: int | None = None,
    ) -> list[Track]:
        from app.repositories.track import (
            TrackRepository,
        )

        track_repo = TrackRepository(self._session)
        seed = await track_repo.get_by_id(
            seed_track_id
        )
        if not seed:
            return []

        candidates = (
            await self._rec_repo.get_candidate_tracks(
                limit=200
            )
        )
        if not candidates:
            return []

        all_tracks = [seed] + candidates
        features = await self._tracks_to_features(
            all_tracks
        )
        seed_feat = features[0]

        history: list[RecListenEvent] = []
        if user_id:
            history = (
                await self._build_listen_history(
                    user_id
                )
            )

        scored = build_radio_queue(
            seed_feat,
            history,
            features[1:],
            queue_size,
        )

        track_map = {t.id: t for t in candidates}
        return [
            track_map[s.track_id]
            for s in scored
            if s.track_id in track_map
        ]

    async def get_global_top(
        self, limit: int = _GLOBAL_TOP_SIZE
    ) -> list[Track]:
        redis = get_redis_client()
        key = f"rec:global_top:{limit}"
        cached = await redis.get(key)
        if cached:
            return await self._rec_repo.get_tracks_by_ids(
                json.loads(cached)
            )
        tracks = await self._rec_repo.get_popular_tracks(
            limit=limit
        )
        await redis.setex(
            key,
            _midnight_ttl(),
            json.dumps([t.id for t in tracks]),
        )
        return tracks

    async def get_daily_playlist(
        self, user_id: int
    ) -> dict:
        redis = get_redis_client()
        key = f"rec:daily:{user_id}"
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)

        user_prefs = await self._build_user_prefs(
            user_id
        )
        history = await self._build_listen_history(
            user_id
        )
        candidates = (
            await self._rec_repo.get_candidate_tracks(
                limit=200
            )
        )
        features = await self._tracks_to_features(
            candidates
        )
        scored = build_daily_mix(
            user_prefs, history, features, _DAILY_SIZE
        )

        from app.services.external_discovery_service import (
            ExternalDiscoveryService,
        )

        external = await ExternalDiscoveryService(
            self._session
        ).discover(user_prefs.preferred_genres)
        int_scored, ext_picked = merge_hybrid_playlist(
            scored, external, _DAILY_SIZE, _EXTERNAL_RATIO
        )

        track_map = {t.id: t for t in candidates}
        internal_ids = [
            s.track_id
            for s in int_scored
            if s.track_id in track_map
        ]
        global_top = await self.get_global_top()

        ttl = _midnight_ttl()
        now = datetime.now(timezone.utc)
        payload: dict = {
            "internal_track_ids": internal_ids,
            "external_suggestions": [
                {
                    "title": e.title,
                    "artist": e.artist,
                    "source": e.source,
                    "external_url": e.external_url,
                    "cover_url": e.cover_url,
                    "duration_seconds": e.duration_seconds,
                }
                for e in ext_picked
            ],
            "global_top_ids": [
                t.id for t in global_top
            ],
            "generated_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=ttl)
            ).isoformat(),
        }
        await redis.setex(
            key, ttl, json.dumps(payload)
        )
        return payload

    async def get_weekly_playlist(
        self, user_id: int
    ) -> dict:
        redis = get_redis_client()
        key = f"rec:weekly:{user_id}"
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)

        user_prefs = await self._build_user_prefs(
            user_id
        )
        history = await self._build_listen_history(
            user_id
        )
        candidates = (
            await self._rec_repo.get_candidate_tracks(
                limit=300
            )
        )
        features = await self._tracks_to_features(
            candidates
        )
        scored = build_weekly_mix(
            user_prefs, history, features, _WEEKLY_SIZE
        )

        from app.services.external_discovery_service import (
            ExternalDiscoveryService,
        )

        external = await ExternalDiscoveryService(
            self._session
        ).discover(
            user_prefs.preferred_genres,
            limit_per_source=20,
        )
        int_scored, ext_picked = merge_hybrid_playlist(
            scored,
            external,
            _WEEKLY_SIZE,
            _EXTERNAL_RATIO,
        )

        track_map = {t.id: t for t in candidates}
        internal_ids = [
            s.track_id
            for s in int_scored
            if s.track_id in track_map
        ]

        ttl = _weekly_ttl()
        now = datetime.now(timezone.utc)
        payload = {
            "internal_track_ids": internal_ids,
            "external_suggestions": [
                {
                    "title": e.title,
                    "artist": e.artist,
                    "source": e.source,
                    "external_url": e.external_url,
                    "cover_url": e.cover_url,
                    "duration_seconds": e.duration_seconds,
                }
                for e in ext_picked
            ],
            "generated_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=ttl)
            ).isoformat(),
        }
        await redis.setex(
            key, ttl, json.dumps(payload)
        )
        return payload

    async def refresh_daily_playlist(
        self, user_id: int
    ) -> dict:
        redis = get_redis_client()
        await redis.delete(f"rec:daily:{user_id}")
        await redis.delete(
            f"rec:global_top:{_GLOBAL_TOP_SIZE}"
        )
        return await self.get_daily_playlist(user_id)
