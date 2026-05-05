import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from dotsound_private_core.services.recommendation_engine import (
    ListenEvent as RecListenEvent,
)
from dotsound_private_core.services.recommendation_engine import (
    MAX_GENRE_MIXES,
    TrackFeatures,
    UserPrefs,
    build_daily_mix,
    build_genre_mixes,
    build_radio_queue,
    build_weekly_mix,
    merge_hybrid_playlist,
    score_tracks_for_user,
    select_similar_tracks,
)
from dotsound_private_core.services.recommendation_language_policy import (
    LOCALE_RU_BONUS,
    cold_start_language_affinity_weights,
    infer_listening_language_code,
    should_boost_russian_discovery,
)
from dotsound_private_core.services.scoring import (
    determine_maturity,
)
from dotsound_private_core.services.signal_policy import (
    IMPLICIT_DISLIKE_MIN_OCCURRENCES,
    IMPLICIT_DISLIKE_QUICK_SKIP_SECONDS,
    IMPLICIT_DISLIKE_WINDOW_DAYS,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.listen_event import ListenEvent as ListenEventModel
from app.models.track import Track
from app.models.user import User
from app.repositories.artist_catalog import (
    ArtistCatalogRepository,
)
from app.repositories.artist_follow import (
    ArtistFollowRepository,
)
from app.repositories.preference import (
    PreferenceRepository,
)
from app.repositories.genre_mix_override import (
    GenreMixOverrideRepository,
)
from app.repositories.recommendation import (
    RecommendationRepository,
)
from app.repositories.signal import (
    ListenEventRepository,
)
from app.services.recsys_telemetry import (
    RecsysTelemetryService,
)
from app.services.track_features_builder import (
    build_track_features,
)

_DAILY_SIZE = 30
_WEEKLY_SIZE = 50
_GLOBAL_TOP_SIZE = 20
_UNSEEN_POOL_LIMIT = 100
_RADIO_CACHE_TTL = 30 * 60


def _midnight_ttl() -> int:
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


def _weekly_ttl() -> int:
    now = datetime.now(UTC)
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
        self._follow_repo = ArtistFollowRepository(
            session
        )
        self._catalog_repo = ArtistCatalogRepository(
            session
        )
        self._telemetry = RecsysTelemetryService(
            session
        )
        self._session = session

    async def _merge_language_affinity(
        self,
        user_id: int,
    ) -> tuple[dict[str, float], str | None]:
        row = await self._session.get(
            User, user_id
        )
        locale = row.locale if row else None
        events = await self._listen_repo.get_recent(
            user_id, limit=200
        )
        tids = {e.track_id for e in events}
        if not tids:
            return (
                cold_start_language_affinity_weights(
                    locale
                ),
                locale,
            )
        tracks = await self._rec_repo.get_tracks_by_ids(
            list(tids)
        )
        by_id = {t.id: t for t in tracks}
        raw: dict[str, float] = defaultdict(float)
        for e in events:
            t = by_id.get(e.track_id)
            if not t:
                continue
            code = infer_listening_language_code(
                t.title, t.artist
            )
            if not code:
                continue
            w = 1.0
            if e.completed:
                w += 0.5
            dur = float(
                e.duration_listened_seconds or 0
            )
            w += min(1.0, dur / 180.0) * 0.25
            raw[code] += w
        if (
            locale
            and str(locale).lower().startswith("ru")
        ):
            raw["ru"] = (
                raw.get("ru", 0.0) + LOCALE_RU_BONUS
            )
        total = sum(raw.values())
        if total <= 0:
            return (
                cold_start_language_affinity_weights(
                    locale
                ),
                locale,
            )
        return (
            {k: v / total for k, v in raw.items()},
            locale,
        )

    async def _build_user_prefs(
        self, user_id: int
    ) -> tuple[UserPrefs, str | None]:
        pref = await self._pref_repo.get_by_user_id(
            user_id
        )
        liked_ids = (
            await self._rec_repo.get_liked_track_ids(
                user_id
            )
        )

        from app.models.dislike import Dislike

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

        implicit_disliked_ids = (
            await self._get_implicit_dislike_ids(
                user_id
            )
        )
        (
            language_aff,
            locale,
        ) = await self._merge_language_affinity(
            user_id
        )

        onboarding_artist_ids: list[int] = (
            (pref.preferred_artist_ids or [])
            if pref
            else []
        )
        followed_artist_ids = (
            await self._follow_repo.list_followed_artist_ids(
                user_id
            )
        )
        merged_artist_ids = list(
            dict.fromkeys(
                onboarding_artist_ids + followed_artist_ids
            )
        )
        similar_artist_ids = (
            await self._catalog_repo.get_similar_artist_ids_from_stations(
                merged_artist_ids
            )
            if merged_artist_ids
            else []
        )

        return (
            UserPrefs(
                preferred_genres=(
                    pref.preferred_genres or []
                    if pref
                    else []
                ),
                preferred_artist_ids=merged_artist_ids,
                similar_artist_ids=similar_artist_ids,
                preferred_moods=(
                    pref.preferred_moods or []
                    if pref
                    else []
                ),
                liked_track_ids=liked_ids,
                disliked_track_ids=disliked_ids,
                implicit_dislike_track_ids=implicit_disliked_ids,
                onboarding_genre_preview_taps=[],
                language_affinity=language_aff,
            ),
            locale,
        )

    async def _scoring_candidate_tracks(
        self,
        user_id: int,
        limit: int,
        genre_filter: list[str] | None,
        user_prefs: UserPrefs,
        user_locale: str | None,
    ) -> list[Track]:
        strat = should_boost_russian_discovery(
            user_prefs.language_affinity,
            user_locale,
        )
        if strat:
            return await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=limit,
                genre_filter=genre_filter,
            )
        return await self._rec_repo.get_candidate_tracks(
            limit=limit,
            genre_filter=genre_filter,
        )

    async def _get_implicit_dislike_ids(
        self, user_id: int
    ) -> set[int]:
        cutoff = datetime.now(
            UTC
        ) - timedelta(
            days=IMPLICIT_DISLIKE_WINDOW_DAYS
        )
        stmt = (
            select(
                ListenEventModel.track_id,
                func.count(
                    ListenEventModel.id
                ).label("c"),
            )
            .where(
                ListenEventModel.user_id == user_id,
                ListenEventModel.skipped.is_(True),
                ListenEventModel.duration_listened_seconds
                < IMPLICIT_DISLIKE_QUICK_SKIP_SECONDS,
                ListenEventModel.created_at
                >= cutoff,
            )
            .group_by(ListenEventModel.track_id)
            .having(
                func.count(ListenEventModel.id)
                >= IMPLICIT_DISLIKE_MIN_OCCURRENCES
            )
        )
        rows = (
            await self._session.execute(stmt)
        ).all()
        return {tid for tid, _ in rows}

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
                created_at=(
                    e.created_at
                    if e.created_at.tzinfo
                    else e.created_at.replace(
                        tzinfo=UTC
                    )
                ),
                duration_listened_seconds=float(
                    e.duration_listened_seconds or 0
                ),
                source_context=e.source_context,
            )
            for e in events
        ]

    async def _tracks_to_features(
        self, tracks: list[Track]
    ) -> list[TrackFeatures]:
        return await build_track_features(
            self._session, tracks
        )

    async def _get_unseen_candidates(
        self,
        user_id: int,
        limit: int = _UNSEEN_POOL_LIMIT,
        genre_filter: list[str] | None = None,
        user_prefs: UserPrefs | None = None,
        user_locale: str | None = None,
    ) -> list[Track]:
        listened = (
            await self._rec_repo.get_listened_track_ids(
                user_id
            )
        )
        ex = listened
        strat = should_boost_russian_discovery(
            user_prefs.language_affinity
            if user_prefs
            else None,
            user_locale,
        )
        if strat:
            return await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=limit,
                genre_filter=genre_filter,
                exclude_ids=ex,
            )
        return await self._rec_repo.get_candidate_tracks(
            limit=limit,
            genre_filter=genre_filter,
            exclude_ids=ex,
        )

    async def _import_external_candidates(
        self,
        candidates: list,
        user_id: int,
    ) -> list[int]:
        from app.config import settings
        from app.services.soundcloud_service import SoundCloudService

        if not candidates or not settings.sc_client_id:
            return []

        sc_svc = SoundCloudService(
            settings.sc_client_id, self._session
        )
        track_ids: list[int] = []
        for c in candidates:
            if not c.external_url:
                continue
            try:
                dur_ms = (
                    c.duration_seconds * 1000
                    if c.duration_seconds
                    else None
                )
                sc_uri = (
                    f"soundcloud:tracks:{c.external_id}"
                    if c.external_id
                    else None
                )
                sc_data: dict[str, Any] = {
                    "permalink_url": c.external_url,
                    "title": c.title,
                    "user": {"username": c.artist or ""},
                    "duration": dur_ms,
                    "artwork_url": c.cover_url,
                    "genre": c.genre,
                    "id": c.external_id,
                    "uri": sc_uri,
                }
                if c.external_id is not None:
                    try:
                        ext_id = int(c.external_id)
                        full = await sc_svc.fetch_track_by_id(ext_id)
                        if isinstance(full, dict):
                            sc_data.update(full)
                    except Exception:
                        pass
                track = await sc_svc.import_or_get_track(
                    sc_data,
                    uploader_id=user_id,
                    skip_background_lyrics=True,
                )
                track_ids.append(track.id)
            except Exception as exc:
                logger.warning(
                    "sc_discovery_import_failed",
                    title=c.title,
                    error=str(exc),
                )
        return track_ids

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
        highlights: list[dict] = []
        highlight_track_ids: set[int] = set()

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
            highlights.append(
                {
                    "track": continue_tracks[0],
                    "label": "Продолжить",
                    "reason": "Вы не дослушали этот трек",
                }
            )
            highlight_track_ids.add(continue_tracks[0].id)

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(
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
        candidates = await self._scoring_candidate_tracks(
            user_id,
            200,
            genre_filter,
            user_prefs,
            user_locale,
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
                # Add to highlights if not already there
                for t in for_you:
                    if t.id not in highlight_track_ids:
                        highlights.append(
                            {
                                "track": t,
                                "label": "Для вас",
                                "reason": "Основано на ваших вкусах",
                            }
                        )
                        highlight_track_ids.add(t.id)
                        break

        if genre_filter:
            popular_genre = candidates[:15]
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

        user_choice = (
            await self.get_user_choice_playlist(
                limit=40
            )
        )
        if user_choice:
            sections.append(
                {
                    "title": "Выбор пользователей",
                    "section_type": "user_choice",
                    "tracks": user_choice,
                }
            )
            # Add to highlights if not already there and we have space
            if len(highlights) < 5:
                for t in user_choice:
                    if t.id not in highlight_track_ids:
                        highlights.append(
                            {
                                "track": t,
                                "label": "Выбор пользователей",
                                "reason": "Популярно в DotSound на этой неделе",
                            }
                        )
                        highlight_track_ids.add(t.id)
                        break

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
                await self._rec_repo.get_candidate_tracks_stratified(
                    total_limit=50,
                )
            )
            sections.append(
                {
                    "title": "Популярное",
                    "section_type": "popular",
                    "tracks": popular,
                }
            )
            if not highlights and popular:
                highlights.append(
                    {
                        "track": popular[0],
                        "label": "Популярное",
                        "reason": "То, что слушают все сейчас",
                    }
                )

        return {
            "sections": sections,
            "highlights": highlights,
            "maturity": maturity,
        }

    async def get_user_choice_playlist(
        self, limit: int = 100
    ) -> list[Track]:
        from dotsound_private_core.services.playcount_policy import (
            UserChoiceTrackInput,
            rank_user_choice_tracks,
        )

        pool = (
            await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=400,
            )
        )
        if not pool:
            return []
        ids = [t.id for t in pool]
        like_map = await self._rec_repo.get_likes_7d_count_by_track_ids(
            ids
        )
        items: list[UserChoiceTrackInput] = [
            UserChoiceTrackInput(
                track_id=t.id,
                play_count=int(t.play_count or 0),
                likes_7d=like_map.get(t.id, 0),
            )
            for t in pool
        ]
        ordered = rank_user_choice_tracks(
            items, limit=limit
        )
        return await self._rec_repo.get_tracks_by_ids(
            ordered
        )

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
            await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=100,
                genre_filter=(
                    [seed.genre]
                    if seed.genre
                    else None
                ),
                exclude_ids={seed.id},
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
        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(
            user_id
        )
        history = (
            await self._build_listen_history(
                user_id
            )
        )

        candidates = await self._scoring_candidate_tracks(
            user_id,
            200,
            None,
            user_prefs,
            user_locale,
        )
        if not candidates:
            return []

        unseen = await self._get_unseen_candidates(
            user_id,
            user_prefs=user_prefs,
            user_locale=user_locale,
        )
        all_tracks = candidates + [
            t
            for t in unseen
            if t.id
            not in {c.id for c in candidates}
        ]
        features = await self._tracks_to_features(
            all_tracks
        )
        feat_by_id = {f.track_id: f for f in features}
        cand_features = [
            feat_by_id[t.id] for t in candidates
        ]
        unseen_features = [
            feat_by_id[t.id]
            for t in unseen
            if t.id in feat_by_id
        ]
        scored = build_daily_mix(
            user_prefs,
            history,
            cand_features,
            size,
            unseen_candidates=unseen_features,
        )

        track_map = {t.id: t for t in all_tracks}
        result = [
            track_map[s.track_id]
            for s in scored
            if s.track_id in track_map
        ]
        await self._telemetry.record_impressions(
            user_id=user_id,
            surface="daily_mix",
            track_ids=[t.id for t in result],
        )
        return result

    async def get_genre_mixes(
        self, user_id: int
    ) -> list[dict]:
        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(user_id)
        history = await self._build_listen_history(
            user_id
        )

        genres: list[str] = list(
            dict.fromkeys(
                user_prefs.preferred_genres
                or []
            )
        )[:MAX_GENRE_MIXES]

        if not genres:
            from app.repositories.track import (
                TrackRepository,
            )

            track_repo = TrackRepository(
                self._session
            )
            all_genres = (
                await track_repo.get_unique_genres()
            )
            genres = all_genres[:MAX_GENRE_MIXES]

        candidates_by_genre: dict[
            str, list[TrackFeatures]
        ] = {}
        for genre in genres:
            pool = await self._scoring_candidate_tracks(
                user_id,
                100,
                [genre],
                user_prefs,
                user_locale,
            )
            if pool:
                feats = (
                    await self._tracks_to_features(
                        pool
                    )
                )
                candidates_by_genre[genre] = feats

        if not candidates_by_genre:
            return []

        mix_results = build_genre_mixes(
            user_prefs, history, candidates_by_genre
        )

        output: list[dict] = []
        for mix in mix_results:
            from app.repositories.track import (
                TrackRepository,
            )

            track_repo = TrackRepository(
                self._session
            )
            tracks = (
                await track_repo.get_by_ids_preserve_order(
                    mix.track_ids
                )
            )
            output.append(
                {
                    "genre": mix.genre,
                    "title": mix.title,
                    "tracks": tracks,
                }
            )

        override_repo = GenreMixOverrideRepository(
            self._session
        )
        overrides = await override_repo.get_by_genres(
            [m["genre"] for m in output]
        )
        overrides_by_genre = {
            row.genre.lower(): row for row in overrides
        }
        for item in output:
            override = overrides_by_genre.get(
                item["genre"].lower()
            )
            if not override:
                continue
            from app.repositories.track import (
                TrackRepository,
            )

            track_repo = TrackRepository(
                self._session
            )
            override_tracks = (
                await track_repo.get_by_ids_preserve_order(
                    [
                        int(tid)
                        for tid in (override.track_ids or [])
                    ]
                )
            )
            if override_tracks:
                item["tracks"] = override_tracks
            item["title"] = override.title

        return output

    async def save_genre_mix_override(
        self,
        *,
        genre: str,
        title: str,
        track_ids: list[int],
        updated_by_id: int,
    ) -> dict:
        from app.repositories.track import (
            TrackRepository,
        )

        clean_genre = genre.strip().lower()
        clean_title = title.strip()
        if not clean_genre:
            raise ValueError("genre is required")
        if not clean_title:
            raise ValueError("title is required")
        if not track_ids:
            raise ValueError("track_ids is required")
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("track_ids must be unique")

        track_repo = TrackRepository(self._session)
        tracks = await track_repo.get_by_ids_preserve_order(
            track_ids
        )
        if len(tracks) != len(track_ids):
            raise ValueError(
                "some tracks were not found"
            )

        override_repo = GenreMixOverrideRepository(
            self._session
        )
        await override_repo.upsert(
            genre=clean_genre,
            title=clean_title,
            track_ids=track_ids,
            updated_by_id=updated_by_id,
        )
        await self._session.commit()
        return {
            "genre": clean_genre,
            "title": clean_title,
            "tracks": tracks,
        }

    async def get_radio(
        self,
        seed_track_id: int,
        queue_size: int = 20,
        user_id: int | None = None,
        exclude_ids: list[int] | None = None,
    ) -> list[Track]:
        from app.repositories.track import (
            TrackRepository,
        )

        redis = get_redis_client()
        cache_key = (
            f"rec:radio:{user_id}:{seed_track_id}"
            if user_id
            else None
        )
        if cache_key:
            cached = await redis.get(cache_key)
            if cached:
                return await self._rec_repo.get_tracks_by_ids(
                    json.loads(cached)
                )

        track_repo = TrackRepository(self._session)
        seed = await track_repo.get_by_id(
            seed_track_id
        )
        if not seed:
            return []

        user_locale: str | None = None
        user_prefs: UserPrefs | None = None
        if user_id:
            (
                user_prefs,
                user_locale,
            ) = await self._build_user_prefs(user_id)

        if user_id and user_prefs is not None:
            candidates = await self._scoring_candidate_tracks(
                user_id,
                200,
                None,
                user_prefs,
                user_locale,
            )
        else:
            candidates = (
                await self._rec_repo.get_candidate_tracks(
                    limit=200
                )
            )
        if not candidates:
            return []

        unseen: list[Track] = []
        if user_id and user_prefs is not None:
            unseen = await self._get_unseen_candidates(
                user_id,
                user_prefs=user_prefs,
                user_locale=user_locale,
            )

        exclude_set = set(exclude_ids or [])
        all_tracks = [seed] + [
            t for t in candidates
            if t.id not in exclude_set
        ] + [
            t
            for t in unseen
            if t.id != seed.id
            and t.id
            not in {c.id for c in candidates}
            and t.id not in exclude_set
        ]
        features = await self._tracks_to_features(
            all_tracks
        )
        feat_by_id = {f.track_id: f for f in features}
        seed_feat = feat_by_id[seed.id]
        cand_features = [
            feat_by_id[t.id]
            for t in candidates
            if t.id != seed.id
        ]
        unseen_features = (
            [
                feat_by_id[t.id]
                for t in unseen
                if t.id in feat_by_id
                and t.id != seed.id
            ]
            if unseen
            else None
        )

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
            cand_features,
            queue_size,
            unseen_candidates=unseen_features,
        )

        track_map = {t.id: t for t in all_tracks}
        result = [
            track_map[s.track_id]
            for s in scored
            if s.track_id in track_map
        ]
        if cache_key and result:
            await redis.setex(
                cache_key,
                _RADIO_CACHE_TTL,
                json.dumps([t.id for t in result]),
            )
        if user_id and result:
            await self._telemetry.record_impressions(
                user_id=user_id,
                surface="radio",
                track_ids=[t.id for t in result],
            )
        return result

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

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(
            user_id
        )
        history = await self._build_listen_history(
            user_id
        )
        candidates = await self._scoring_candidate_tracks(
            user_id,
            200,
            None,
            user_prefs,
            user_locale,
        )
        unseen = await self._get_unseen_candidates(
            user_id,
            user_prefs=user_prefs,
            user_locale=user_locale,
        )
        all_tracks = candidates + [
            t
            for t in unseen
            if t.id
            not in {c.id for c in candidates}
        ]
        features = await self._tracks_to_features(
            all_tracks
        )
        feat_by_id = {f.track_id: f for f in features}
        cand_features = [
            feat_by_id[t.id] for t in candidates
        ]
        unseen_features = [
            feat_by_id[t.id]
            for t in unseen
            if t.id in feat_by_id
        ]
        scored = build_daily_mix(
            user_prefs,
            history,
            cand_features,
            _DAILY_SIZE,
            unseen_candidates=unseen_features,
        )

        from app.services.external_discovery_service import (
            ExternalDiscoveryService,
        )

        external = await ExternalDiscoveryService(
            self._session
        ).discover(
            user_prefs.preferred_genres,
            language_affinity=user_prefs.language_affinity,
            user_locale=user_locale,
        )
        int_scored, ext_picked = merge_hybrid_playlist(
            scored, external, _DAILY_SIZE
        )

        track_map = {t.id: t for t in all_tracks}
        internal_ids = [
            s.track_id
            for s in int_scored
            if s.track_id in track_map
        ]
        global_top = await self.get_global_top()
        external_track_ids = await self._import_external_candidates(
            ext_picked, user_id
        )
        await self._telemetry.record_impressions(
            user_id=user_id,
            surface="daily_playlist",
            track_ids=internal_ids
            + external_track_ids,
        )

        ttl = _midnight_ttl()
        now = datetime.now(UTC)
        payload: dict = {
            "internal_track_ids": internal_ids,
            "external_track_ids": external_track_ids,
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

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(
            user_id
        )
        history = await self._build_listen_history(
            user_id
        )
        candidates = await self._scoring_candidate_tracks(
            user_id,
            300,
            None,
            user_prefs,
            user_locale,
        )
        unseen = await self._get_unseen_candidates(
            user_id,
            limit=150,
            user_prefs=user_prefs,
            user_locale=user_locale,
        )
        all_tracks = candidates + [
            t
            for t in unseen
            if t.id
            not in {c.id for c in candidates}
        ]
        features = await self._tracks_to_features(
            all_tracks
        )
        feat_by_id = {f.track_id: f for f in features}
        cand_features = [
            feat_by_id[t.id] for t in candidates
        ]
        unseen_features = [
            feat_by_id[t.id]
            for t in unseen
            if t.id in feat_by_id
        ]
        scored = build_weekly_mix(
            user_prefs,
            history,
            cand_features,
            _WEEKLY_SIZE,
            unseen_candidates=unseen_features,
        )

        from app.services.external_discovery_service import (
            ExternalDiscoveryService,
        )

        external = await ExternalDiscoveryService(
            self._session
        ).discover(
            user_prefs.preferred_genres,
            limit_per_source=20,
            language_affinity=user_prefs.language_affinity,
            user_locale=user_locale,
        )
        int_scored, ext_picked = merge_hybrid_playlist(
            scored,
            external,
            _WEEKLY_SIZE,
        )

        track_map = {t.id: t for t in all_tracks}
        internal_ids = [
            s.track_id
            for s in int_scored
            if s.track_id in track_map
        ]
        external_track_ids = await self._import_external_candidates(
            ext_picked, user_id
        )
        await self._telemetry.record_impressions(
            user_id=user_id,
            surface="weekly_playlist",
            track_ids=internal_ids
            + external_track_ids,
        )

        ttl = _weekly_ttl()
        now = datetime.now(UTC)
        payload = {
            "internal_track_ids": internal_ids,
            "external_track_ids": external_track_ids,
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
