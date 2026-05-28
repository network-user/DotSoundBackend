import asyncio
import hashlib
import importlib
import json
from collections import defaultdict
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import structlog
from dotsound_private_core.services.playback_health_policy import (
    should_exclude_from_autoplay_queue,
)
from dotsound_private_core.services.radio_policy import (
    radio_seed_artist_pool_limit,
    radio_seed_embedding_pool_limit,
    radio_seed_genre_pool_limit,
    radio_seed_similarity_pool_limit,
    should_include_seed_artist_pool,
)
from dotsound_private_core.services.recommendation_engine import (
    MAX_GENRE_MIXES,
    ExternalTrackCandidate,
    RadioTuning,
    TasteWeight,
    TrackFeatures,
    UserPrefs,
    build_audio_taste_vector,
    build_daily_mix,
    build_genre_mixes,
    build_radio_queue,
    build_weekly_mix,
    interleave_personalized_by_familiarity,
    merge_hybrid_playlist,
    normalize_artist_taste_weights,
    normalize_genre_taste_weights,
    normalize_radio_tuning,
    score_tracks_for_user,
    select_similar_tracks,
)
from dotsound_private_core.services.recommendation_engine import (
    ListenEvent as RecListenEvent,
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
from dotsound_private_core.services.user_top_policy import (
    ArtistAggregate,
    GenreAggregate,
    rank_user_top_artists,
    rank_user_top_genres,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import radio_request_observed
from app.core.redis import get_redis_client
from app.models.listen_event import ListenEvent as ListenEventModel
from app.models.track import Track
from app.models.user import User
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.artist_catalog import (
    ArtistCatalogRepository,
)
from app.repositories.artist_follow import (
    ArtistFollowRepository,
)
from app.repositories.embedding import EmbeddingRepository
from app.repositories.genre_mix_override import (
    GenreMixOverrideRepository,
)
from app.repositories.preference import (
    PreferenceRepository,
)
from app.repositories.recommendation import (
    RecommendationRepository,
)
from app.repositories.signal import (
    ListenEventRepository,
)
from app.services.ab_assignment_service import (
    ABAssignmentService,
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
_EXTERNAL_DISCOVERY_TIMEOUT = 8
_EXTERNAL_IMPORT_TIMEOUT = 15
_GENRE_MIXES_CACHE_TTL = 3 * 60 * 60
_GENRE_MIXES_CACHE_PATTERN = "rec:genre_mixes:*"
_HOME_CACHE_TTL = 10 * 60
_HOME_SECTION_TITLES = {
    "continue": "Продолжить слушать",
    "personalized": "Для вас",
    "new_releases": "Новые релизы",
    "genre_popular": "Популярное",
    "user_choice": "Выбор пользователей",
    "fav_artists": "Любимые исполнители",
    "popular": "Популярное",
}


def _dedupe_sections_cross_section(
    sections: list[dict[str, Any]],
    *,
    min_section_size: int,
    highlight_track_ids: set[int],
) -> list[dict[str, Any]]:
    """Remove tracks already shown in earlier sections (or in highlights).

    Sections are processed in their existing priority order; the first
    occurrence of each track wins. A section that ends up below
    ``min_section_size`` is dropped entirely to avoid sparse rows.
    """
    seen: set[int] = set(highlight_track_ids)
    result: list[dict[str, Any]] = []
    for section in sections:
        tracks = section.get("tracks") or []
        deduped: list[Any] = []
        for track in tracks:
            tid = getattr(track, "id", None)
            if tid is None or tid in seen:
                continue
            seen.add(tid)
            deduped.append(track)
        if len(deduped) >= min_section_size:
            section = {**section, "tracks": deduped}
            result.append(section)
    return result


async def _purge_genre_mixes_cache() -> int:
    redis = get_redis_client()
    keys: list[str] = []
    async for key in redis.scan_iter(_GENRE_MIXES_CACHE_PATTERN, count=200):
        keys.append(key)
    if keys:
        await redis.delete(*keys)
    logger.info("genre_mixes_cache_purged", count=len(keys))
    return len(keys)


_RADIO_CACHE_TTL = 30 * 60
_RADIO_SKIP_GUARD_SECONDS = 1
_RADIO_LAST_QUEUE_TTL = 20
_RADIO_TUNING_KEY = "recsys.radio_tuning"
_DIVERSITY_RERANK_KEY = "recsys.diversity_rerank"
_DEFAULT_DIVERSITY_LAMBDA = 0.7
_RETRIEVAL_BLEND_KEY = "recsys.retrieval_blend"
_RADIO_SESSION_KEY_PREFIX = "radio:session:"
_RADIO_SESSION_TTL = 3600
_RADIO_SESSION_BUFFER = 96
_RADIO_MERGED_EXCLUDE_CAP = 280
_RADIO_USER_SUPPLEMENT_LIMIT = 80
_RADIO_SIMILAR_ARTIST_CAP = 25
_DAILY_NOVELTY_TARGET = 0.4
_WEEKLY_NOVELTY_TARGET = 0.5
_SEQUENTIAL_RADIO_KEY = "recsys.sequential_radio"
_DEFAULT_SEQUENTIAL_BLEND_WEIGHT = 0.45


def _midnight_ttl() -> int:
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


def _weekly_ttl() -> int:
    now = datetime.now(UTC)
    days_ahead = (7 - now.weekday()) % 7 or 7
    next_monday = (now + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((next_monday - now).total_seconds()))


def _weekly_top_ttl() -> int:
    return 30 * 60


logger = structlog.get_logger(__name__)


def _radio_playback_candidate_allowed(track: object) -> bool:
    if should_exclude_from_autoplay_queue(
        playback_suppressed_until=getattr(
            track,
            "playback_suppressed_until",
            None,
        ),
        playback_recovery_failed_at=getattr(
            track,
            "playback_recovery_failed_at",
            None,
        ),
    ):
        return False

    has_playback_attrs = any(
        hasattr(track, attr)
        for attr in (
            "access_mode",
            "file_key",
            "hls_manifest_key",
        )
    )
    if not has_playback_attrs:
        return True

    access_mode = getattr(track, "access_mode", None)
    if access_mode == "third_party_stream":
        return True
    if access_mode == "internal_stream":
        return bool(
            getattr(track, "file_key", None)
            or getattr(track, "hls_manifest_key", None)
        )
    return bool(getattr(track, "file_key", None))


def _filter_radio_playback_candidates(tracks: list[Track]) -> list[Track]:
    return [t for t in tracks if _radio_playback_candidate_allowed(t)]


def _merge_track_groups(
    groups: list[list[Track]],
    *,
    limit: int,
) -> list[Track]:
    out: list[Track] = []
    seen: set[int] = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for track in group:
            track_id = getattr(track, "id", None)
            if not isinstance(track_id, int) or track_id in seen:
                continue
            seen.add(track_id)
            out.append(track)
            if len(out) >= limit:
                return out
    return out


def _loads_dict_payload(raw: str | bytes | bytearray) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self._rec_repo = RecommendationRepository(session)
        self._pref_repo = PreferenceRepository(session)
        self._listen_repo = ListenEventRepository(session)
        self._follow_repo = ArtistFollowRepository(session)
        self._catalog_repo = ArtistCatalogRepository(session)
        self._embedding_repo = EmbeddingRepository(session)
        self._telemetry = RecsysTelemetryService(session)
        self._session = session

    async def _merge_language_affinity(
        self,
        user_id: int,
    ) -> tuple[dict[str, float], str | None]:
        row = await self._session.get(User, user_id)
        locale = row.locale if row else None
        events = await self._listen_repo.get_recent(user_id, limit=200)
        tids = {e.track_id for e in events}
        if not tids:
            return (
                cold_start_language_affinity_weights(locale),
                locale,
            )
        tracks = await self._rec_repo.get_tracks_by_ids(list(tids))
        by_id = {t.id: t for t in tracks}
        raw: dict[str, float] = defaultdict(float)
        for e in events:
            t = by_id.get(e.track_id)
            if not t:
                continue
            code = infer_listening_language_code(t.title, t.artist)
            if not code:
                continue
            w = 1.0
            if e.completed:
                w += 0.5
            dur = float(e.duration_listened_seconds or 0)
            w += min(1.0, dur / 180.0) * 0.25
            raw[code] += w
        if locale and str(locale).lower().startswith("ru"):
            raw["ru"] = raw.get("ru", 0.0) + LOCALE_RU_BONUS
        total = sum(raw.values())
        if total <= 0:
            return (
                cold_start_language_affinity_weights(locale),
                locale,
            )
        return (
            {k: v / total for k, v in raw.items()},
            locale,
        )

    async def _build_user_prefs(
        self, user_id: int
    ) -> tuple[UserPrefs, str | None]:
        pref = await self._pref_repo.get_by_user_id(user_id)
        liked_raw = await self._rec_repo.get_liked_track_ids(user_id)
        liked_ids: set[int] = (
            set(liked_raw)
            if isinstance(liked_raw, set | list | tuple)
            else set()
        )

        from app.models.dislike import Dislike

        dislike_result = await self._session.execute(
            select(Dislike.track_id).where(Dislike.user_id == user_id)
        )
        disliked_ids = set(dislike_result.scalars().all())

        implicit_disliked_ids = await self._get_implicit_dislike_ids(user_id)
        (
            language_aff,
            locale,
        ) = await self._merge_language_affinity(user_id)

        onboarding_artist_ids: list[int] = (
            (pref.preferred_artist_ids or []) if pref else []
        )
        followed_artist_ids = await self._follow_repo.list_followed_artist_ids(
            user_id
        )
        genre_rows_raw = await self._rec_repo.get_user_genre_listen_aggregates(
            user_id
        )
        artist_rows_raw = (
            await self._rec_repo.get_user_artist_listen_aggregates(user_id)
        )
        genre_rows = genre_rows_raw if isinstance(genre_rows_raw, list) else []
        artist_rows = (
            artist_rows_raw if isinstance(artist_rows_raw, list) else []
        )
        ranked_genres = rank_user_top_genres(
            [
                GenreAggregate(
                    genre=str(genre),
                    completed_listens=int(count),
                )
                for genre, count in genre_rows
            ]
        )
        ranked_artists = rank_user_top_artists(
            [
                ArtistAggregate(
                    artist_id=int(artist_id),
                    completed_listens=int(count),
                    distinct_tracks=int(distinct_tracks),
                )
                for artist_id, count, distinct_tracks in artist_rows
            ]
        )
        learned_genres = [str(item.key) for item in ranked_genres]
        learned_artist_ids = [int(item.key) for item in ranked_artists]
        behavior_genre_weights = normalize_genre_taste_weights(
            [TasteWeight(item.key, item.score) for item in ranked_genres]
        )
        behavior_artist_weights = normalize_artist_taste_weights(
            [TasteWeight(item.key, item.score) for item in ranked_artists]
        )
        merged_artist_ids = list(
            dict.fromkeys(
                onboarding_artist_ids
                + followed_artist_ids
                + learned_artist_ids
            )
        )
        preferred_genres = list(
            dict.fromkeys(
                (pref.preferred_genres or [] if pref else []) + learned_genres
            )
        )
        if merged_artist_ids:
            cat_repo = self._catalog_repo
            (
                similar_artist_ids,
                similar_artist_weights,
            ) = await cat_repo.get_similar_artist_recommendation_signals(
                merged_artist_ids,
            )
        else:
            similar_artist_ids = []
            similar_artist_weights = {}

        repeated_raw = await self._rec_repo.get_repeat_listen_counts(
            user_id,
            days=60,
            min_count=2,
        )
        repeated_ids = (
            set(repeated_raw.keys())
            if isinstance(repeated_raw, dict)
            else set()
        )
        taste_seed_ids = sorted(liked_ids | repeated_ids)[:40]
        taste_audio_vector: list[float] | None = None
        if taste_seed_ids:
            taste_tracks = await self._rec_repo.get_tracks_by_ids(
                taste_seed_ids
            )
            if isinstance(taste_tracks, list) and taste_tracks:
                taste_features = await self._tracks_to_features(taste_tracks)
                taste_audio_vector = build_audio_taste_vector(
                    [
                        f.audio_feature_vector
                        for f in taste_features
                        if f.audio_feature_vector
                    ]
                )

        return (
            UserPrefs(
                preferred_genres=preferred_genres,
                preferred_artist_ids=merged_artist_ids,
                followed_artist_ids=list(followed_artist_ids),
                similar_artist_ids=similar_artist_ids,
                similar_artist_weights=similar_artist_weights,
                behavior_genre_weights=behavior_genre_weights,
                behavior_artist_weights=behavior_artist_weights,
                taste_audio_vector=taste_audio_vector,
                preferred_moods=(pref.preferred_moods or [] if pref else []),
                liked_track_ids=liked_ids,
                disliked_track_ids=disliked_ids,
                implicit_dislike_track_ids=implicit_disliked_ids,
                onboarding_genre_preview_taps=[],
                language_affinity=language_aff,
            ),
            locale,
        )

    async def _append_artist_scoring_groups(
        self,
        groups: list[list[Track]],
        *,
        artist_ids: list[int],
        limit: int,
        exclude_ids: set[int] | None,
    ) -> None:
        if not artist_ids:
            return
        ex = exclude_ids
        try:
            artist_tracks = await self._rec_repo.get_tracks_by_artist_ids(
                artist_ids,
                limit=limit,
            )
            if artist_tracks:
                groups.append(artist_tracks)
            similar_to_artist_tracks = (
                await self._rec_repo
                .get_track_similarity_candidates_for_artist_ids(
                    artist_ids,
                    limit=max(50, limit),
                    exclude_ids=ex if ex else None,
                )
            )
            if similar_to_artist_tracks:
                groups.append(similar_to_artist_tracks)
        except SQLAlchemyError as exc:
            logger.warning(
                "scoring_artist_candidate_pool_failed",
                artist_count=len(artist_ids),
                error=str(exc),
            )

    async def _scoring_candidate_tracks(
        self,
        user_id: int,
        limit: int,
        genre_filter: list[str] | None,
        user_prefs: UserPrefs,
        user_locale: str | None,
        exclude_ids: set[int] | None = None,
    ) -> list[Track]:
        strat = should_boost_russian_discovery(
            user_prefs.language_affinity,
            user_locale,
        )
        ex = set(exclude_ids) if exclude_ids else set()
        if strat:
            base = await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=limit,
                genre_filter=genre_filter,
                exclude_ids=ex,
            )
        else:
            base = await self._rec_repo.get_candidate_tracks(
                limit=limit,
                genre_filter=genre_filter,
                exclude_ids=ex if ex else None,
            )

        groups: list[list[Track]] = [base if isinstance(base, list) else []]
        artist_ids = user_prefs.preferred_artist_ids[:20]
        if artist_ids:
            await self._append_artist_scoring_groups(
                groups,
                artist_ids=artist_ids,
                limit=max(40, limit // 2),
                exclude_ids=ex if ex else None,
            )

        similar_artist_ids = user_prefs.similar_artist_ids[:30]
        if similar_artist_ids:
            try:
                similar_artist_tracks = (
                    await self._rec_repo.get_tracks_by_artist_ids(
                        similar_artist_ids,
                        limit=max(40, limit // 2),
                    )
                )
                if similar_artist_tracks:
                    groups.append(similar_artist_tracks)
            except SQLAlchemyError as exc:
                logger.warning(
                    "scoring_similar_artist_pool_failed",
                    artist_count=len(similar_artist_ids),
                    error=str(exc),
                )

        learned_genres = user_prefs.preferred_genres[:4]
        if not genre_filter and learned_genres:
            per_genre_limit = max(20, limit // max(1, len(learned_genres)))
            for genre in learned_genres:
                genre_tracks = await self._rec_repo.get_candidate_tracks(
                    limit=per_genre_limit,
                    genre_filter=[genre],
                    exclude_ids=ex if ex else None,
                )
                if isinstance(genre_tracks, list):
                    groups.append(genre_tracks)

        recent_genres = genre_filter or user_prefs.preferred_genres[:5] or None
        recent_tracks = await self._rec_repo.get_recent_candidate_tracks(
            days=45,
            limit=max(30, limit // 2),
            genre_filter=recent_genres,
            exclude_ids=ex if ex else None,
        )
        if isinstance(recent_tracks, list):
            groups.append(recent_tracks)

        return _merge_track_groups(
            groups,
            limit=max(limit, min(limit * 2, 500)),
        )

    async def _get_implicit_dislike_ids(self, user_id: int) -> set[int]:
        cutoff = datetime.now(UTC) - timedelta(
            days=IMPLICIT_DISLIKE_WINDOW_DAYS
        )
        stmt = (
            select(
                ListenEventModel.track_id,
                func.count(ListenEventModel.id).label("c"),
            )
            .where(
                ListenEventModel.user_id == user_id,
                ListenEventModel.skipped.is_(True),
                ListenEventModel.duration_listened_seconds
                < IMPLICIT_DISLIKE_QUICK_SKIP_SECONDS,
                ListenEventModel.created_at >= cutoff,
            )
            .group_by(ListenEventModel.track_id)
            .having(
                func.count(ListenEventModel.id)
                >= IMPLICIT_DISLIKE_MIN_OCCURRENCES
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return {tid for tid, _ in rows}

    async def _build_listen_history(
        self, user_id: int
    ) -> list[RecListenEvent]:
        events = await self._listen_repo.get_recent(user_id, limit=200)
        return [
            RecListenEvent(
                track_id=e.track_id,
                completed=e.completed,
                skipped=e.skipped,
                created_at=(
                    e.created_at
                    if e.created_at.tzinfo
                    else e.created_at.replace(tzinfo=UTC)
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
        return await build_track_features(self._session, tracks)

    async def _get_unseen_candidates(
        self,
        user_id: int,
        limit: int = _UNSEEN_POOL_LIMIT,
        genre_filter: list[str] | None = None,
        user_prefs: UserPrefs | None = None,
        user_locale: str | None = None,
    ) -> list[Track]:
        listened = await self._rec_repo.get_listened_track_ids(user_id)
        ex = listened
        effective_genres = genre_filter
        if effective_genres is None and user_prefs is not None:
            effective_genres = user_prefs.preferred_genres[:5] or None
        strat = should_boost_russian_discovery(
            user_prefs.language_affinity if user_prefs else None,
            user_locale,
        )
        if strat:
            base = await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=limit,
                genre_filter=effective_genres,
                exclude_ids=ex,
            )
        else:
            base = await self._rec_repo.get_candidate_tracks(
                limit=limit,
                genre_filter=effective_genres,
                exclude_ids=ex,
            )
        recent = await self._rec_repo.get_recent_candidate_tracks(
            days=45,
            limit=limit,
            genre_filter=effective_genres,
            exclude_ids=ex,
        )
        return _merge_track_groups(
            [
                base if isinstance(base, list) else [],
                recent if isinstance(recent, list) else [],
            ],
            limit=limit,
        )

    async def _cold_start_fallback_tracks(
        self,
        *,
        size: int,
        exclude_ids: set[int] | None = None,
    ) -> list[Track]:
        if size <= 0:
            return []
        pool_limit = max(size * 4, 60)
        pool = await self._rec_repo.get_popular_tracks(limit=pool_limit)
        excluded = exclude_ids or set()
        pool = [t for t in pool if t.id not in excluded]
        if not pool:
            return []

        buckets: dict[str, list[Track]] = defaultdict(list)
        for track in pool:
            key = (track.genre or "_other").lower()
            buckets[key].append(track)

        result: list[Track] = []
        seen_ids: set[int] = set()
        while len(result) < size:
            picked_this_round = False
            for key in list(buckets.keys()):
                if buckets[key]:
                    track = buckets[key].pop(0)
                    if track.id in seen_ids:
                        continue
                    seen_ids.add(track.id)
                    result.append(track)
                    picked_this_round = True
                    if len(result) >= size:
                        break
            if not picked_this_round:
                break
        return result[:size]

    async def _import_external_candidates(
        self,
        candidates: list[ExternalTrackCandidate],
        user_id: int,
        max_concurrency: int = 2,
    ) -> list[int]:
        from app.config import settings
        from app.services.soundcloud_service import SoundCloudService

        if not candidates or not settings.sc_client_id:
            return []

        sc_svc = SoundCloudService(settings.sc_client_id, self._session)
        sem = asyncio.Semaphore(max_concurrency)

        async def _import_one(c: ExternalTrackCandidate) -> int | None:
            if not c.external_url:
                return None
            async with sem:
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
                        skip_playback_verify=True,
                    )
                    return track.id
                except Exception as exc:
                    logger.warning(
                        "sc_discovery_import_failed",
                        title=c.title,
                        error=str(exc),
                    )
                    return None

        results = await asyncio.gather(*[_import_one(c) for c in candidates])
        return [tid for tid in results if tid is not None]

    async def get_home_sections(self, user_id: int) -> dict[str, Any]:
        redis = get_redis_client()
        cache_key = f"rec:home:{user_id}"
        cached = await redis.get(cache_key)
        if cached:
            rebuilt = await self._rebuild_home_from_cache(cached)
            if rebuilt is not None:
                return rebuilt

        pref = await self._pref_repo.get_by_user_id(user_id)
        listen_count = await self._listen_repo.count_for_user(user_id)

        maturity = determine_maturity(
            onboarding_completed=(bool(pref and pref.onboarding_completed)),
            calibration_completed=(bool(pref and pref.calibration_completed)),
            enrichment_done=False,
            listen_count=listen_count,
        )

        sections: list[dict[str, Any]] = []
        highlights: list[dict[str, Any]] = []
        highlight_track_ids: set[int] = set()

        continue_tracks = await self._rec_repo.get_incomplete_listens(
            user_id, limit=10
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
        ) = await self._build_user_prefs(user_id)
        history = await self._build_listen_history(user_id)

        genre_filter = (
            pref.preferred_genres if pref and pref.preferred_genres else None
        )
        try:
            candidates = await self._scoring_candidate_tracks(
                user_id,
                200,
                genre_filter,
                user_prefs,
                user_locale,
            )
        except SQLAlchemyError as exc:
            logger.warning(
                "home_scoring_candidates_failed",
                user_id=user_id,
                error=str(exc),
            )
            candidates = []

        if candidates:
            features = await self._tracks_to_features(candidates)
            scored = score_tracks_for_user(user_prefs, history, features)
            listened_ids = await self._rec_repo.get_listened_track_ids(
                user_id
            )
            interleaved = interleave_personalized_by_familiarity(
                scored,
                listened_ids,
                target_size=20,
            )
            track_map = {t.id: t for t in candidates}
            for_you = [
                track_map[s.track_id]
                for s in interleaved
                if s.track_id in track_map
            ]
            if for_you:
                sections.append(
                    {
                        "title": "Для вас",
                        "section_type": ("personalized"),
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
                title = f"Популярное: " f"{genre_filter[0]}"
                sections.append(
                    {
                        "title": title,
                        "section_type": ("genre_popular"),
                        "tracks": popular_genre,
                    }
                )

        recent = await self._rec_repo.get_recent_tracks(days=7, limit=15)
        if recent:
            sections.append(
                {
                    "title": "Новые релизы",
                    "section_type": "new_releases",
                    "tracks": recent,
                }
            )

        user_choice = await self.get_user_choice_playlist(limit=40)
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
                                "reason": (
                                    "Популярно в DotSound на этой неделе"
                                ),
                            }
                        )
                        highlight_track_ids.add(t.id)
                        break

        if user_prefs.preferred_artist_ids:
            artist_tracks = await self._rec_repo.get_tracks_by_artist_ids(
                user_prefs.preferred_artist_ids,
                limit=15,
            )
            if artist_tracks:
                sections.append(
                    {
                        "title": ("Любимые исполнители"),
                        "section_type": ("fav_artists"),
                        "tracks": artist_tracks,
                    }
                )

        if not sections:
            popular = await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=50,
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

        sections = _dedupe_sections_cross_section(
            sections,
            min_section_size=3,
            highlight_track_ids=highlight_track_ids,
        )

        if sections:
            await redis.setex(
                cache_key,
                _HOME_CACHE_TTL,
                json.dumps(
                    self._serialize_home_payload(
                        sections, highlights, maturity
                    )
                ),
            )

        return {
            "sections": sections,
            "highlights": highlights,
            "maturity": maturity,
        }

    def _serialize_home_payload(
        self,
        sections: list[dict[str, Any]],
        highlights: list[dict[str, Any]],
        maturity: str,
    ) -> dict[str, Any]:
        return {
            "sections": [
                {
                    "title": s["title"],
                    "section_type": s["section_type"],
                    "track_ids": [t.id for t in s["tracks"]],
                }
                for s in sections
            ],
            "highlights": [
                {
                    "track_id": h["track"].id,
                    "label": h["label"],
                    "reason": h.get("reason"),
                }
                for h in highlights
            ],
            "maturity": maturity,
        }

    async def _rebuild_home_from_cache(
        self, cached: str
    ) -> dict[str, Any] | None:
        from app.repositories.track import TrackRepository

        try:
            raw = json.loads(cached)
        except (TypeError, ValueError):
            return None

        all_ids: list[int] = []
        seen_ids: set[int] = set()
        for s in raw.get("sections", []):
            for tid in s.get("track_ids", []):
                if tid not in seen_ids:
                    seen_ids.add(tid)
                    all_ids.append(tid)
        for h in raw.get("highlights", []):
            tid = h.get("track_id")
            if isinstance(tid, int) and tid not in seen_ids:
                seen_ids.add(tid)
                all_ids.append(tid)

        if not all_ids:
            return None

        track_repo = TrackRepository(self._session)
        fetched = await track_repo.get_by_ids_preserve_order(all_ids)
        by_id = {t.id: t for t in fetched}

        sections: list[dict[str, Any]] = []
        for s in raw.get("sections", []):
            section_tracks = [
                by_id[tid] for tid in s.get("track_ids", []) if tid in by_id
            ]
            sections.append(
                {
                    "title": s.get("title", ""),
                    "section_type": s.get("section_type", ""),
                    "tracks": section_tracks,
                }
            )

        highlights: list[dict[str, Any]] = []
        for h in raw.get("highlights", []):
            tid = h.get("track_id")
            if not isinstance(tid, int):
                continue
            track = by_id.get(tid)
            if track is None:
                continue
            highlights.append(
                {
                    "track": track,
                    "label": h.get("label", ""),
                    "reason": h.get("reason"),
                }
            )

        return {
            "sections": sections,
            "highlights": highlights,
            "maturity": raw.get("maturity", "cold"),
        }

    async def get_home_section(
        self,
        user_id: int,
        section_type: str,
        limit: int = 15,
    ) -> dict[str, Any]:
        size = max(1, min(int(limit), 50))
        if section_type not in _HOME_SECTION_TITLES:
            raise ValueError("Unknown home section")

        if section_type == "continue":
            tracks = await self._rec_repo.get_incomplete_listens(
                user_id, limit=size
            )
            return {
                "title": _HOME_SECTION_TITLES[section_type],
                "section_type": section_type,
                "tracks": tracks,
            }

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(user_id)

        if section_type == "new_releases":
            tracks = await self._rec_repo.get_recent_tracks(days=7, limit=size)
            return {
                "title": _HOME_SECTION_TITLES[section_type],
                "section_type": section_type,
                "tracks": tracks,
            }

        if section_type == "user_choice":
            tracks = await self.get_user_choice_playlist(limit=size)
            return {
                "title": _HOME_SECTION_TITLES[section_type],
                "section_type": section_type,
                "tracks": tracks,
            }

        if section_type == "fav_artists":
            tracks = []
            if user_prefs.preferred_artist_ids:
                tracks = await self._rec_repo.get_tracks_by_artist_ids(
                    user_prefs.preferred_artist_ids,
                    limit=size,
                )
            return {
                "title": _HOME_SECTION_TITLES[section_type],
                "section_type": section_type,
                "tracks": tracks,
            }

        if section_type == "popular":
            tracks = await self._rec_repo.get_candidate_tracks_stratified(
                total_limit=size,
            )
            return {
                "title": _HOME_SECTION_TITLES[section_type],
                "section_type": section_type,
                "tracks": tracks,
            }

        pref = await self._pref_repo.get_by_user_id(user_id)
        genre_filter = (
            pref.preferred_genres if pref and pref.preferred_genres else None
        )
        candidates = await self._scoring_candidate_tracks(
            user_id,
            max(100, size * 6),
            genre_filter,
            user_prefs,
            user_locale,
        )

        if section_type == "genre_popular":
            title = _HOME_SECTION_TITLES[section_type]
            if genre_filter:
                title = f"Популярное: {genre_filter[0]}"
            return {
                "title": title,
                "section_type": section_type,
                "tracks": candidates[:size] if genre_filter else [],
            }

        history = await self._build_listen_history(user_id)
        features = await self._tracks_to_features(candidates)
        scored = score_tracks_for_user(user_prefs, history, features)
        scored_ids = [s.track_id for s in scored[:size]]
        track_map = {t.id: t for t in candidates}
        tracks = [track_map[tid] for tid in scored_ids if tid in track_map]
        return {
            "title": _HOME_SECTION_TITLES[section_type],
            "section_type": section_type,
            "tracks": tracks,
        }

    async def get_user_choice_playlist(self, limit: int = 100) -> list[Track]:
        from dotsound_private_core.services.playcount_policy import (
            UserChoiceTrackInput,
            rank_user_choice_tracks,
        )

        pool = await self._rec_repo.get_candidate_tracks_stratified(
            total_limit=400,
        )
        if not pool:
            return await self._cold_start_fallback_tracks(size=limit)
        ids = [t.id for t in pool]
        like_map = await self._rec_repo.get_likes_7d_count_by_track_ids(ids)
        items: list[UserChoiceTrackInput] = [
            UserChoiceTrackInput(
                track_id=t.id,
                play_count=int(t.play_count or 0),
                likes_7d=like_map.get(t.id, 0),
            )
            for t in pool
        ]
        ordered = rank_user_choice_tracks(items, limit=limit)
        result = await self._rec_repo.get_tracks_by_ids(ordered)
        if not result:
            return await self._cold_start_fallback_tracks(size=limit)
        return result

    async def get_weekly_top_playlist(
        self,
        limit: int = 50,
    ) -> dict[str, Any]:
        from dotsound_private_core.services.weekly_top_policy import (
            WEEKLY_TOP_DEFAULT_LIMIT,
            WEEKLY_TOP_SCORE_VERSION,
            WEEKLY_TOP_WINDOW_DAYS,
            WeeklyTopTrackInput,
            rank_weekly_top_tracks,
        )

        size = max(
            1,
            min(int(limit), WEEKLY_TOP_DEFAULT_LIMIT * 2),
        )
        redis = get_redis_client()
        cache_key = f"rec:weekly-top:{size}"
        try:
            cached = await redis.get(cache_key)
        except Exception as exc:
            logger.warning(
                "weekly_top_cache_get_fail",
                err=str(exc),
            )
            cached = None
        if cached:
            cached_payload = _loads_dict_payload(cached)
            if cached_payload is not None:
                cached_payload["from_cache"] = True
                return cached_payload

        listens_map = await self._rec_repo.get_qualified_listens_7d_counts(
            days=WEEKLY_TOP_WINDOW_DAYS,
            candidate_pool_limit=max(400, size * 6),
        )
        track_ids = list(listens_map.keys())
        likes_map: dict[int, int] = {}
        if track_ids:
            likes_map = await self._rec_repo.get_likes_7d_count_by_track_ids(
                track_ids
            )
        items = [
            WeeklyTopTrackInput(
                track_id=tid,
                listens_7d=listens_map.get(tid, 0),
                likes_7d=likes_map.get(tid, 0),
            )
            for tid in track_ids
        ]
        ordered_ids = rank_weekly_top_tracks(items, limit=size)
        if not ordered_ids:
            fallback = await self._cold_start_fallback_tracks(size=size)
            ordered_ids = [t.id for t in fallback]
        now = datetime.now(UTC)
        ttl = _weekly_top_ttl()
        payload: dict[str, Any] = {
            "track_ids": ordered_ids,
            "score_version": WEEKLY_TOP_SCORE_VERSION,
            "window_days": WEEKLY_TOP_WINDOW_DAYS,
            "generated_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "from_cache": False,
        }
        try:
            await redis.set(
                cache_key,
                json.dumps(payload),
                ex=ttl,
            )
        except Exception as exc:
            logger.warning(
                "weekly_top_cache_set_fail",
                err=str(exc),
            )
        return payload

    async def get_forgotten_treasures_playlist(
        self,
        user_id: int,
        limit: int = 50,
    ) -> dict[str, Any]:
        from dotsound_private_core.services.forgotten_treasures_policy import (
            FORGOTTEN_DEFAULT_LIMIT,
            FORGOTTEN_MAX_LIMIT,
            FORGOTTEN_MIN_LIKE_AGE_DAYS,
            FORGOTTEN_SILENCE_DAYS,
            FORGOTTEN_TREASURES_SCORE_VERSION,
            ForgottenTrackInput,
            rank_forgotten_treasure_tracks,
        )

        sized = FORGOTTEN_DEFAULT_LIMIT if limit <= 0 else limit
        size = max(1, min(int(sized), FORGOTTEN_MAX_LIMIT))
        now = datetime.now(UTC)
        like_cutoff = now - timedelta(days=FORGOTTEN_MIN_LIKE_AGE_DAYS)
        silence_cutoff = now - timedelta(days=FORGOTTEN_SILENCE_DAYS)
        rows = await self._rec_repo.list_forgotten_treasure_rows(
            user_id,
            like_cutoff=like_cutoff,
            silence_cutoff=silence_cutoff,
            fetch_cap=max(600, size * 25),
        )
        inputs = [
            ForgottenTrackInput(
                track_id=tid,
                like_created_at=liked_at,
                last_listen_at=last_at,
            )
            for tid, liked_at, last_at in rows
        ]
        ordered_ids = rank_forgotten_treasure_tracks(
            inputs,
            now=now,
            limit=size,
        )
        return {
            "track_ids": ordered_ids,
            "score_version": FORGOTTEN_TREASURES_SCORE_VERSION,
            "min_like_age_days": FORGOTTEN_MIN_LIKE_AGE_DAYS,
            "silence_days": FORGOTTEN_SILENCE_DAYS,
            "generated_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=900)).isoformat(),
        }

    async def get_similar(self, track_id: int, limit: int = 10) -> list[Track]:
        from app.repositories.artist import (
            ArtistRepository,
        )
        from app.repositories.track import (
            TrackRepository,
        )

        track_repo = TrackRepository(self._session)
        seed = await track_repo.get_by_id(track_id)
        if not seed:
            return []

        artist_repo = ArtistRepository(self._session)
        linked = await artist_repo.get_track_artists(track_id)
        seed_artist_ids = [a.id for a in linked]

        neighbor_ids: list[int] = []
        if seed_artist_ids:
            catalog_repo = self._catalog_repo
            neighbor_ids = (
                await catalog_repo.get_station_neighbor_track_ids_for_artists(
                    seed_artist_ids,
                    exclude_track_ids=frozenset({seed.id}),
                    limit=120,
                )
            )

        candidates = await self._rec_repo.get_candidate_tracks_stratified(
            total_limit=100,
            genre_filter=([seed.genre] if seed.genre else None),
            exclude_ids={seed.id},
        )

        neighbor_pick = [tid for tid in neighbor_ids if tid != seed.id][:80]
        extra_tracks: list[Track] = []
        if neighbor_pick:
            extra_tracks = await self._rec_repo.get_tracks_by_ids(
                neighbor_pick
            )

        indexed_tracks = await self._rec_repo.get_track_similarity_candidates(
            seed.id,
            limit=max(limit * 4, 40),
            exclude_ids={seed.id},
        )

        embedding_neighbors = await self._embedding_repo.find_neighbors(
            seed_track_id=seed.id,
            k=max(limit * 2, 30),
            exclude_ids={seed.id},
        )
        embedding_track_ids = [tid for tid, _ in embedding_neighbors]
        embedding_tracks: list[Track] = []
        if embedding_track_ids:
            embedding_tracks = await self._rec_repo.get_tracks_by_ids(
                embedding_track_ids
            )

        by_id: dict[int, Track] = {t.id: t for t in candidates}
        for t in extra_tracks:
            by_id.setdefault(t.id, t)
        for t in indexed_tracks:
            by_id.setdefault(t.id, t)
        for t in embedding_tracks:
            by_id.setdefault(t.id, t)
        merged_candidates = list(by_id.values())

        if not merged_candidates:
            return []

        all_tracks = [seed] + merged_candidates
        features = await self._tracks_to_features(all_tracks)
        seed_feat = features[0]
        candidate_feats = features[1:]

        scored = select_similar_tracks(
            seed_feat,
            candidate_feats,
            limit=limit,
            station_neighbor_track_ids=(
                frozenset(neighbor_ids) if neighbor_ids else None
            ),
        )
        track_map = {t.id: t for t in merged_candidates}
        return [
            track_map[s.track_id] for s in scored if s.track_id in track_map
        ]

    async def get_daily_mix(self, user_id: int, size: int = 30) -> list[Track]:
        redis = get_redis_client()
        cache_key = f"rec:daily_mix:{user_id}"
        cached = await redis.get(cache_key)
        if cached:
            ids: list[int] = json.loads(cached)
            return await self._rec_repo.get_tracks_by_ids(ids)

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(user_id)
        history = await self._build_listen_history(user_id)

        candidates = await self._scoring_candidate_tracks(
            user_id,
            200,
            None,
            user_prefs,
            user_locale,
        )
        if not candidates:
            fallback = await self._cold_start_fallback_tracks(size=size)
            if fallback:
                await redis.setex(
                    cache_key,
                    _midnight_ttl(),
                    json.dumps([t.id for t in fallback]),
                )
            return fallback

        unseen = await self._get_unseen_candidates(
            user_id,
            user_prefs=user_prefs,
            user_locale=user_locale,
        )
        all_tracks = candidates + [
            t for t in unseen if t.id not in {c.id for c in candidates}
        ]
        features = await self._tracks_to_features(all_tracks)
        feat_by_id = {f.track_id: f for f in features}
        cand_features = [feat_by_id[t.id] for t in candidates]
        unseen_features = [
            feat_by_id[t.id] for t in unseen if t.id in feat_by_id
        ]
        rerank_enabled, rerank_lambda = await self._load_diversity_rerank(
            user_id=user_id
        )
        scored = build_daily_mix(
            user_prefs,
            history,
            cand_features,
            size,
            novelty_target=_DAILY_NOVELTY_TARGET,
            unseen_candidates=unseen_features,
            use_diversity_rerank=rerank_enabled,
            diversity_lambda=rerank_lambda,
        )

        track_map = {t.id: t for t in all_tracks}
        result = [
            track_map[s.track_id] for s in scored if s.track_id in track_map
        ]
        if not result:
            result = await self._cold_start_fallback_tracks(size=size)
        if await self._load_retrieval_blend_enabled(user_id=user_id):
            existing_ids = {t.id for t in result}
            blend_ids = await self._retrieval_blend_track_ids(
                user_id=user_id,
                size=size,
                exclude_ids=existing_ids,
            )
            blend_tracks = await self._rec_repo.get_tracks_by_ids(blend_ids)
            blend_by_id = {t.id: t for t in blend_tracks}
            ordered_blend = [
                blend_by_id[tid] for tid in blend_ids if tid in blend_by_id
            ]
            result = (result + ordered_blend)[:size]
        algo_version = await self._algorithm_version_with_arm(
            experiment_key="daily_mix",
            user_id=user_id,
        )
        await self._telemetry.record_impressions(
            user_id=user_id,
            surface="daily_mix",
            track_ids=[t.id for t in result],
            algorithm_version=algo_version,
        )
        if result:
            await redis.setex(
                cache_key,
                _midnight_ttl(),
                json.dumps([t.id for t in result]),
            )
        return result

    async def get_genre_mixes(self, user_id: int) -> list[dict[str, Any]]:
        redis = get_redis_client()
        cache_key = f"rec:genre_mixes:{user_id}"
        cached = await redis.get(cache_key)
        if cached:
            raw_items: list[dict[str, Any]] = json.loads(cached)
            all_ids: list[int] = []
            seen_ids: set[int] = set()
            for item in raw_items:
                for tid in item["track_ids"]:
                    if tid not in seen_ids:
                        seen_ids.add(tid)
                        all_ids.append(tid)
            fetched = await self._rec_repo.get_tracks_by_ids(all_ids)
            by_id = {t.id: t for t in fetched}
            output: list[dict[str, Any]] = []
            for item in raw_items:
                tracks = [
                    by_id[tid] for tid in item["track_ids"] if tid in by_id
                ]
                output.append(
                    {
                        "genre": item["genre"],
                        "title": item["title"],
                        "tracks": tracks,
                    }
                )
            return output

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(user_id)
        history = await self._build_listen_history(user_id)

        genres: list[str] = list(
            dict.fromkeys(user_prefs.preferred_genres or [])
        )[:MAX_GENRE_MIXES]

        if not genres:
            from app.repositories.track import (
                TrackRepository,
            )

            track_repo = TrackRepository(self._session)
            all_genres = await track_repo.get_unique_genres()
            genres = all_genres[:MAX_GENRE_MIXES]

        candidates_by_genre: dict[str, list[TrackFeatures]] = {}
        for genre in genres:
            pool = await self._scoring_candidate_tracks(
                user_id,
                100,
                [genre],
                user_prefs,
                user_locale,
            )
            if pool:
                feats = await self._tracks_to_features(pool)
                candidates_by_genre[genre] = feats

        if not candidates_by_genre:
            return []

        mix_results = build_genre_mixes(
            user_prefs, history, candidates_by_genre
        )

        fresh_output: list[dict[str, Any]] = []
        for mix in mix_results:
            from app.repositories.track import (
                TrackRepository,
            )

            track_repo = TrackRepository(self._session)
            tracks = await track_repo.get_by_ids_preserve_order(mix.track_ids)
            fresh_output.append(
                {
                    "genre": mix.genre,
                    "title": mix.title,
                    "tracks": tracks,
                }
            )

        override_repo = GenreMixOverrideRepository(self._session)
        overrides = await override_repo.get_by_genres(
            [m["genre"] for m in fresh_output]
        )
        overrides_by_genre = {row.genre.lower(): row for row in overrides}
        for item in fresh_output:
            override = overrides_by_genre.get(item["genre"].lower())
            if not override:
                continue
            from app.repositories.track import (
                TrackRepository,
            )

            track_repo = TrackRepository(self._session)
            override_tracks = await track_repo.get_by_ids_preserve_order(
                [int(tid) for tid in (override.track_ids or [])]
            )
            if override_tracks:
                item["tracks"] = override_tracks
            item["title"] = override.title

        if fresh_output:
            payload = [
                {
                    "genre": item["genre"],
                    "title": item["title"],
                    "track_ids": [t.id for t in item["tracks"]],
                }
                for item in fresh_output
            ]
            await redis.setex(
                cache_key,
                _GENRE_MIXES_CACHE_TTL,
                json.dumps(payload),
            )

        return fresh_output

    async def get_genre_mix(
        self,
        user_id: int,
        genre: str,
    ) -> dict[str, Any] | None:
        clean_genre = genre.strip().lower()
        if not clean_genre:
            return None

        from app.repositories.track import (
            TrackRepository,
        )

        track_repo = TrackRepository(self._session)
        override_repo = GenreMixOverrideRepository(self._session)
        override = await override_repo.get_by_genre(clean_genre)

        tracks: list[Track] = []
        title = f"Mix: {clean_genre[:1].upper()}{clean_genre[1:]}"

        if override is not None:
            override_tracks = await track_repo.get_by_ids_preserve_order(
                [int(tid) for tid in (override.track_ids or [])]
            )
            if override_tracks:
                tracks = override_tracks
            title = override.title

        if not tracks:
            (
                user_prefs,
                user_locale,
            ) = await self._build_user_prefs(user_id)
            history = await self._build_listen_history(user_id)
            pool = await self._scoring_candidate_tracks(
                user_id,
                100,
                [clean_genre],
                user_prefs,
                user_locale,
            )
            if pool:
                feats = await self._tracks_to_features(pool)
                mixes = build_genre_mixes(
                    user_prefs,
                    history,
                    {clean_genre: feats},
                )
                if mixes:
                    mix = mixes[0]
                    tracks = await track_repo.get_by_ids_preserve_order(
                        mix.track_ids
                    )
                    if override is None:
                        title = mix.title

        if not tracks:
            return None

        return {
            "genre": clean_genre,
            "title": title,
            "tracks": tracks,
        }

    async def save_genre_mix_override(
        self,
        *,
        genre: str,
        title: str,
        track_ids: list[int],
        updated_by_id: int,
    ) -> dict[str, Any]:
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
        tracks = await track_repo.get_by_ids_preserve_order(track_ids)
        if len(tracks) != len(track_ids):
            raise ValueError("some tracks were not found")

        override_repo = GenreMixOverrideRepository(self._session)
        await override_repo.upsert(
            genre=clean_genre,
            title=clean_title,
            track_ids=track_ids,
            updated_by_id=updated_by_id,
        )
        await self._session.commit()
        await _purge_genre_mixes_cache()
        return {
            "genre": clean_genre,
            "title": clean_title,
            "tracks": tracks,
        }

    async def get_radio_with_freshness(
        self,
        seed_track_id: int,
        queue_size: int = 20,
        user_id: int | None = None,
        exclude_ids: list[int] | None = None,
    ) -> tuple[list[Track], dict[int, str]]:
        tracks = await self.get_radio(
            seed_track_id=seed_track_id,
            queue_size=queue_size,
            user_id=user_id,
            exclude_ids=exclude_ids,
        )
        if not tracks:
            return tracks, {}
        if user_id is None:
            return tracks, {t.id: "familiar" for t in tracks}
        freshness = await self.compute_freshness_for_tracks(
            user_id=user_id,
            track_ids=[t.id for t in tracks],
            seed_track_id=seed_track_id,
        )
        return tracks, freshness

    async def compute_freshness_for_tracks(
        self,
        *,
        user_id: int,
        track_ids: list[int],
        seed_track_id: int | None = None,
    ) -> dict[int, str]:
        if not track_ids:
            return {}
        listened = await self._rec_repo.get_listened_track_ids(user_id)
        familiar_ids = [tid for tid in track_ids if tid in listened]
        last_played = (
            await self._rec_repo.get_last_played_at_for_tracks(
                user_id, familiar_ids
            )
            if familiar_ids
            else {}
        )
        radio_tuning = await self._load_radio_tuning(user_id=user_id)
        rediscovery_cutoff = datetime.now(UTC) - timedelta(
            days=radio_tuning.rediscovery_days
        )
        freshness: dict[int, str] = {}
        for tid in track_ids:
            if seed_track_id is not None and tid == seed_track_id:
                freshness[tid] = "seed"
            elif tid in listened:
                last_seen = last_played.get(tid)
                if last_seen is not None and last_seen <= rediscovery_cutoff:
                    freshness[tid] = "rediscovery"
                else:
                    freshness[tid] = "familiar"
            else:
                freshness[tid] = "new"
        return freshness

    async def _collect_radio_seed_candidate_groups(
        self,
        seed: Track,
        *,
        seed_artist_ids: list[int],
        exclude_ids: set[int],
        queue_size: int,
    ) -> tuple[list[list[Track]], list[int]]:
        exclude_for_seed = set(exclude_ids) | {seed.id}
        sim_limit = radio_seed_similarity_pool_limit(queue_size)
        emb_limit = radio_seed_embedding_pool_limit(queue_size)
        artist_pool_limit = radio_seed_artist_pool_limit(queue_size)
        genre_limit = radio_seed_genre_pool_limit(queue_size)
        groups: list[list[Track]] = []
        station_neighbor_ids: list[int] = []

        indexed_tracks = await self._rec_repo.get_track_similarity_candidates(
            seed.id,
            limit=sim_limit,
            exclude_ids=exclude_for_seed,
        )
        if indexed_tracks:
            groups.append(indexed_tracks)

        embedding_neighbors = await self._embedding_repo.find_neighbors(
            seed_track_id=seed.id,
            k=emb_limit,
            exclude_ids=exclude_for_seed,
        )
        embedding_track_ids = [tid for tid, _ in embedding_neighbors]
        if embedding_track_ids:
            embedding_tracks = await self._rec_repo.get_tracks_by_ids(
                embedding_track_ids
            )
            if embedding_tracks:
                groups.append(embedding_tracks)

        if should_include_seed_artist_pool(seed_artist_ids):
            station_neighbor_ids = (
                await self._catalog_repo
                .get_station_neighbor_track_ids_for_artists(
                    seed_artist_ids,
                    exclude_track_ids=frozenset({seed.id}),
                    limit=200,
                )
            )
            if station_neighbor_ids:
                neighbor_tracks = await self._rec_repo.get_tracks_by_ids(
                    station_neighbor_ids
                )
                if neighbor_tracks:
                    groups.append(neighbor_tracks)

            similar_artist_ids, _ = (
                await self._catalog_repo
                .get_similar_artist_recommendation_signals(seed_artist_ids)
            )
            seed_artist_set = set(seed_artist_ids)
            related_artist_ids = [
                aid
                for aid in similar_artist_ids
                if aid not in seed_artist_set
            ][:_RADIO_SIMILAR_ARTIST_CAP]
            if related_artist_ids:
                similar_artist_tracks = (
                    await self._rec_repo
                    .get_track_similarity_candidates_for_artist_ids(
                        related_artist_ids,
                        limit=sim_limit,
                        exclude_ids=exclude_for_seed,
                    )
                )
                if similar_artist_tracks:
                    groups.append(similar_artist_tracks)

            cross_artist_similar = (
                await self._rec_repo
                .get_track_similarity_candidates_for_artist_ids(
                    seed_artist_ids,
                    limit=sim_limit,
                    exclude_ids=exclude_for_seed,
                )
            )
            if cross_artist_similar:
                groups.append(cross_artist_similar)

            raw_same_artist = await self._rec_repo.get_tracks_by_artist_ids(
                seed_artist_ids,
                limit=max(artist_pool_limit, 80),
            )
            same_artist = [
                t
                for t in raw_same_artist
                if t.id not in exclude_for_seed
            ]
            if same_artist:
                features = await self._tracks_to_features(
                    [seed] + same_artist
                )
                seed_feat = features[0]
                cand_feats = [
                    f for f in features[1:] if f.track_id != seed.id
                ]
                if cand_feats:
                    scored_same = select_similar_tracks(
                        seed_feat,
                        cand_feats,
                        limit=artist_pool_limit,
                        station_neighbor_track_ids=(
                            frozenset(station_neighbor_ids)
                            if station_neighbor_ids
                            else None
                        ),
                    )
                    track_map = {t.id: t for t in same_artist}
                    picked = [
                        track_map[row.track_id]
                        for row in scored_same
                        if row.track_id in track_map
                    ]
                    if picked:
                        groups.append(picked)

        seed_genre = getattr(seed, "genre", None)
        if seed_genre:
            seed_genre_tracks = (
                await self._rec_repo.get_candidate_tracks_stratified(
                    total_limit=genre_limit,
                    genre_filter=[seed_genre],
                    exclude_ids=exclude_for_seed,
                )
            )
            if seed_genre_tracks:
                groups.append(seed_genre_tracks)

        return groups, station_neighbor_ids

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
        merged_exclude: set[int] = {
            int(tid)
            for tid in (exclude_ids or [])
            if int(tid) > 0 and int(tid) != seed_track_id
        }
        if user_id:
            for tid in await self._load_radio_session(user_id=user_id):
                if tid > 0 and tid != seed_track_id:
                    merged_exclude.add(tid)
        exclude_normalized = sorted(merged_exclude)[:_RADIO_MERGED_EXCLUDE_CAP]
        exclude_hash = hashlib.blake2b(
            ",".join(str(tid) for tid in exclude_normalized).encode(),
            digest_size=8,
        ).hexdigest()
        cache_key = None
        last_key = None
        if user_id:
            cache_key = f"rec:radio:{user_id}:{seed_track_id}:{exclude_hash}"
            last_key = f"rec:radio:last:{user_id}:{seed_track_id}"
            guard_key = f"rec:radio:guard:{user_id}:{seed_track_id}"
            can_fetch = await redis.set(
                guard_key,
                "1",
                ex=_RADIO_SKIP_GUARD_SECONDS,
                nx=True,
            )
            if not can_fetch and last_key:
                guarded = await redis.get(last_key)
                if guarded:
                    tracks = await self._rec_repo.get_tracks_by_ids(
                        json.loads(guarded)
                    )
                    before_filter = len(tracks)
                    tracks = _filter_radio_playback_candidates(tracks)
                    if len(tracks) != before_filter:
                        logger.info(
                            "radio_cached_filtered_unplayable",
                            source="guarded",
                            removed=before_filter - len(tracks),
                            remaining=len(tracks),
                        )
                    if merged_exclude:
                        before_exclude = len(tracks)
                        tracks = [
                            t for t in tracks if t.id not in merged_exclude
                        ]
                        if len(tracks) != before_exclude:
                            logger.info(
                                "radio_guard_filtered_excluded",
                                removed=before_exclude - len(tracks),
                                remaining=len(tracks),
                            )
                    if not tracks:
                        guarded = None
                if guarded:
                    radio_request_observed(
                        surface="recommendations_radio",
                        outcome="guarded",
                        queue_size=len(tracks),
                        guard_hit=True,
                    )
                    return tracks
        if cache_key:
            cached = await redis.get(cache_key)
            if cached:
                tracks = await self._rec_repo.get_tracks_by_ids(
                    json.loads(cached)
                )
                before_filter = len(tracks)
                tracks = _filter_radio_playback_candidates(tracks)
                if len(tracks) != before_filter:
                    logger.info(
                        "radio_cached_filtered_unplayable",
                        source="cache",
                        removed=before_filter - len(tracks),
                        remaining=len(tracks),
                    )
                if not tracks:
                    cached = None
            if cached:
                radio_request_observed(
                    surface="recommendations_radio",
                    outcome="cache_hit",
                    queue_size=len(tracks),
                )
                return tracks

        track_repo = TrackRepository(self._session)
        seed = await track_repo.get_by_id(seed_track_id)
        if not seed:
            radio_request_observed(
                surface="recommendations_radio",
                outcome="seed_not_found",
                queue_size=0,
            )
            return []

        user_locale: str | None = None
        user_prefs: UserPrefs | None = None
        radio_tuning: RadioTuning | None = None
        if user_id:
            (
                user_prefs,
                user_locale,
            ) = await self._build_user_prefs(user_id)
            radio_tuning = await self._load_radio_tuning(user_id=user_id)

        from app.repositories.artist import ArtistRepository

        artist_repo = ArtistRepository(self._session)
        seed_artists = await artist_repo.get_track_artists(seed.id)
        seed_artist_ids = [a.id for a in seed_artists]

        seed_groups, station_neighbor_ids = (
            await self._collect_radio_seed_candidate_groups(
                seed,
                seed_artist_ids=seed_artist_ids,
                exclude_ids=set(exclude_normalized),
                queue_size=queue_size,
            )
        )

        user_supplement: list[Track] = []
        if user_id and user_prefs is not None:
            try:
                user_supplement = await self._scoring_candidate_tracks(
                    user_id,
                    _RADIO_USER_SUPPLEMENT_LIMIT,
                    None,
                    user_prefs,
                    user_locale,
                    exclude_ids=set(exclude_normalized),
                )
            except SQLAlchemyError as exc:
                logger.warning(
                    "radio_scoring_candidates_failed",
                    user_id=user_id,
                    seed_track_id=seed_track_id,
                    error=str(exc),
                )
        else:
            user_supplement = await self._rec_repo.get_candidate_tracks(
                limit=_RADIO_USER_SUPPLEMENT_LIMIT,
                exclude_ids=(
                    set(exclude_normalized) if exclude_normalized else None
                ),
            )

        merge_groups = seed_groups + (
            [user_supplement] if user_supplement else []
        )
        candidates = _merge_track_groups(
            merge_groups,
            limit=max(200, queue_size * 16),
        )
        before_filter = len(candidates)
        candidates = _filter_radio_playback_candidates(candidates)
        if len(candidates) != before_filter:
            logger.info(
                "radio_candidates_filtered_unplayable",
                removed=before_filter - len(candidates),
                remaining=len(candidates),
            )
        unseen: list[Track] = []
        if user_id and user_prefs is not None:
            unseen = await self._get_unseen_candidates(
                user_id,
                user_prefs=user_prefs,
                user_locale=user_locale,
            )
            unseen_before_filter = len(unseen)
            unseen = _filter_radio_playback_candidates(unseen)
            if len(unseen) != unseen_before_filter:
                logger.info(
                    "radio_unseen_filtered_unplayable",
                    removed=unseen_before_filter - len(unseen),
                    remaining=len(unseen),
                )
        if not candidates and not unseen:
            radio_request_observed(
                surface="recommendations_radio",
                outcome="no_candidates",
                queue_size=0,
            )
            return []

        exclude_set = set(exclude_normalized)
        all_tracks = (
            [seed]
            + [t for t in candidates if t.id not in exclude_set]
            + [
                t
                for t in unseen
                if t.id != seed.id
                and t.id not in {c.id for c in candidates}
                and t.id not in exclude_set
            ]
        )
        features = await self._tracks_to_features(all_tracks)
        feat_by_id = {f.track_id: f for f in features}
        seed_feat = feat_by_id[seed.id]
        cand_features = [
            feat_by_id[t.id]
            for t in candidates
            if t.id != seed.id
            and t.id in feat_by_id
            and t.id not in exclude_set
        ]
        unseen_features = (
            [
                feat_by_id[t.id]
                for t in unseen
                if t.id in feat_by_id
                and t.id != seed.id
                and t.id not in exclude_set
            ]
            if unseen
            else None
        )

        history: list[RecListenEvent] = []
        if user_id:
            history = await self._build_listen_history(user_id)

        rerank_enabled, rerank_lambda = await self._load_diversity_rerank(
            user_id=user_id
        )
        scored = build_radio_queue(
            seed_feat,
            history,
            cand_features,
            queue_size,
            unseen_candidates=unseen_features,
            tuning=radio_tuning,
            station_neighbor_track_ids=(
                frozenset(station_neighbor_ids)
                if station_neighbor_ids
                else None
            ),
            liked_track_ids=(
                user_prefs.liked_track_ids if user_prefs else None
            ),
            disliked_track_ids=(
                user_prefs.disliked_track_ids if user_prefs else None
            ),
            use_diversity_rerank=rerank_enabled,
            diversity_lambda=rerank_lambda,
        )

        track_map = {t.id: t for t in all_tracks}
        result = [
            track_map[s.track_id] for s in scored if s.track_id in track_map
        ]
        if cache_key and result:
            await redis.setex(
                cache_key,
                _RADIO_CACHE_TTL,
                json.dumps([t.id for t in result]),
            )
            if last_key:
                await redis.setex(
                    last_key,
                    _RADIO_LAST_QUEUE_TTL,
                    json.dumps([t.id for t in result]),
                )
        if user_id and result:
            algo_version = await self._algorithm_version_with_arm(
                experiment_key="radio",
                user_id=user_id,
            )
            await self._telemetry.record_impressions(
                user_id=user_id,
                surface="radio",
                track_ids=[t.id for t in result],
                algorithm_version=algo_version,
            )
        seq_enabled, seq_weight = await self._load_sequential_radio_settings(
            user_id=user_id
        )
        if seq_enabled and result:
            result = await self._apply_sequential_blend(
                baseline_tracks=result,
                seed_track_id=seed_track_id,
                user_id=user_id,
                weight=seq_weight,
            )
        if user_id and result:
            await self._push_radio_session(
                user_id=user_id,
                track_ids=[t.id for t in result],
            )
        radio_request_observed(
            surface="recommendations_radio",
            outcome="fresh",
            queue_size=len(result),
        )
        return result

    async def _algorithm_version_with_arm(
        self,
        *,
        experiment_key: str,
        user_id: int | None,
    ) -> str | None:
        from dotsound_private_core.services.recommendation_engine import (
            get_algorithm_version,
        )

        if user_id is None:
            return None
        ab_service = ABAssignmentService(self._session)
        assignment = await ab_service.get_assignment(
            experiment_key=experiment_key,
            user_id=user_id,
        )
        if assignment is None:
            return None
        base_version = get_algorithm_version()
        return f"{experiment_key}:{assignment.arm}|{base_version}"

    async def _load_sequential_radio_settings(
        self, *, user_id: int | None
    ) -> tuple[bool, float]:
        repo = AppSettingsRepository(self._session)
        raw = await repo.get_value(_SEQUENTIAL_RADIO_KEY, default={})
        if not isinstance(raw, dict):
            return False, _DEFAULT_SEQUENTIAL_BLEND_WEIGHT
        if not bool(raw.get("enabled", False)):
            return False, _DEFAULT_SEQUENTIAL_BLEND_WEIGHT
        weight_raw = raw.get("blend_weight", _DEFAULT_SEQUENTIAL_BLEND_WEIGHT)
        try:
            weight = float(weight_raw)
        except (TypeError, ValueError):
            weight = _DEFAULT_SEQUENTIAL_BLEND_WEIGHT
        weight = max(0.0, min(1.0, weight))
        if user_id is None:
            return True, weight
        split_raw = raw.get("ab_split_percent_b", 100)
        try:
            split_int = int(split_raw)
        except (TypeError, ValueError):
            split_int = 100
        split_int = max(0, min(100, split_int))
        if (user_id % 100) < split_int:
            return True, weight
        return False, weight

    async def _push_radio_session(
        self,
        *,
        user_id: int | None,
        track_ids: list[int],
    ) -> None:
        if not user_id or not track_ids:
            return
        redis = get_redis_client()
        key = f"{_RADIO_SESSION_KEY_PREFIX}{user_id}"
        try:
            for tid in track_ids:
                await cast(
                    Awaitable[int],
                    redis.lpush(key, str(int(tid))),
                )
            await cast(
                Awaitable[str],
                redis.ltrim(key, 0, _RADIO_SESSION_BUFFER - 1),
            )
            await redis.expire(key, _RADIO_SESSION_TTL)
        except Exception:
            logger.warning(
                "radio_session_push_failed",
                exc_info=True,
                user_id=user_id,
            )

    async def _load_radio_session(
        self,
        *,
        user_id: int | None,
    ) -> list[int]:
        if not user_id:
            return []
        redis = get_redis_client()
        key = f"{_RADIO_SESSION_KEY_PREFIX}{user_id}"
        try:
            raw_items = await cast(
                Awaitable[list[Any]],
                redis.lrange(key, 0, _RADIO_SESSION_BUFFER - 1),
            )
        except Exception:
            return []
        out: list[int] = []
        for item in raw_items:
            value = item.decode() if isinstance(item, bytes) else str(item)
            try:
                out.append(int(value))
            except (TypeError, ValueError):
                continue
        return list(reversed(out))

    async def _apply_sequential_blend(
        self,
        *,
        baseline_tracks: list[Track],
        seed_track_id: int,
        user_id: int | None,
        weight: float,
    ) -> list[Track]:
        if not baseline_tracks:
            return baseline_tracks
        recent = await self._load_radio_session(user_id=user_id)
        if not recent:
            return baseline_tracks
        from dotsound_private_core.services.sequential_policy import (
            SessionContext,
            blend_with_baseline,
            trim_session_window,
        )

        try:
            ranker_module = importlib.import_module(
                "worker.audio.session_ranker"
            )
            default_session_ranker = getattr(
                ranker_module,
                "default_session_ranker",
                None,
            )
        except Exception:
            return baseline_tracks
        if not callable(default_session_ranker):
            return baseline_tracks
        ranker = default_session_ranker()
        context = SessionContext(
            user_id=user_id,
            recent_track_ids=trim_session_window(recent),
            seed_track_id=seed_track_id,
        )
        candidate_ids = [t.id for t in baseline_tracks]
        sequential_scores = ranker.rank_session_continuation(
            context, candidate_ids
        )
        baseline_scores = {
            t.id: 1.0 / (idx + 1) for idx, t in enumerate(baseline_tracks)
        }
        blended = blend_with_baseline(
            baseline_scores,
            sequential_scores,
            sequential_weight=weight,
        )
        track_map = {t.id: t for t in baseline_tracks}
        return [track_map[tid] for tid, _ in blended if tid in track_map]

    async def _load_retrieval_blend_enabled(
        self, *, user_id: int | None
    ) -> bool:
        repo = AppSettingsRepository(self._session)
        raw = await repo.get_value(_RETRIEVAL_BLEND_KEY, default={})
        if not isinstance(raw, dict):
            return False
        if not bool(raw.get("enabled", False)):
            return False
        if user_id is None:
            return True
        split_raw = raw.get("ab_split_percent_b", 100)
        try:
            split_int = int(split_raw)
        except (TypeError, ValueError):
            split_int = 100
        split_int = max(0, min(100, split_int))
        return (user_id % 100) < split_int

    async def _retrieval_blend_track_ids(
        self,
        *,
        user_id: int,
        size: int,
        exclude_ids: set[int],
    ) -> list[int]:
        from dotsound_private_core.services.retrieval_policy import (
            CandidateBundle,
            CandidateSource,
            RetrievedCandidate,
            merge_candidate_sources,
        )

        user_neighbors = (
            await self._embedding_repo.find_track_candidates_for_user(
                user_id=user_id,
                k=size * 4,
                exclude_ids=exclude_ids,
            )
        )
        if not user_neighbors:
            return []
        bundle = CandidateBundle(
            source=CandidateSource.USER_EMBEDDING,
            candidates=tuple(
                RetrievedCandidate(
                    track_id=int(tid),
                    score=float(score),
                    source=CandidateSource.USER_EMBEDDING,
                )
                for tid, score in user_neighbors
            ),
        )
        merged = merge_candidate_sources(
            [bundle],
            output_size=size,
        )
        return [c.track_id for c in merged]

    async def _load_diversity_rerank(
        self, *, user_id: int | None
    ) -> tuple[bool, float | None]:
        repo = AppSettingsRepository(self._session)
        raw = await repo.get_value(_DIVERSITY_RERANK_KEY, default={})
        if not isinstance(raw, dict):
            return False, None
        if not bool(raw.get("enabled", False)):
            return False, None

        lambda_raw = raw.get("diversity_lambda", _DEFAULT_DIVERSITY_LAMBDA)
        try:
            lambda_value = float(lambda_raw)
        except (TypeError, ValueError):
            lambda_value = _DEFAULT_DIVERSITY_LAMBDA
        lambda_value = max(0.0, min(1.0, lambda_value))

        if user_id is None:
            return True, lambda_value

        split_raw = raw.get("ab_split_percent_b", 100)
        try:
            split_int = int(split_raw)
        except (TypeError, ValueError):
            split_int = 100
        split_int = max(0, min(100, split_int))
        bucket = user_id % 100
        if bucket < split_int:
            return True, lambda_value
        return False, None

    async def _load_radio_tuning(self, *, user_id: int) -> RadioTuning:
        repo = AppSettingsRepository(self._session)
        raw = await repo.get_value(_RADIO_TUNING_KEY, default={})
        if not isinstance(raw, dict):
            return normalize_radio_tuning(None)

        enabled = bool(raw.get("enabled", False))
        if not enabled:
            return normalize_radio_tuning(None)

        split = raw.get("ab_split_percent_b", 50)
        try:
            split_int = int(split)
        except (TypeError, ValueError):
            split_int = 50
        split_int = max(0, min(100, split_int))
        bucket = user_id % 100
        variant_key = "variant_b" if bucket < split_int else "variant_a"
        variant = raw.get(variant_key)
        if not isinstance(variant, dict):
            variant = raw.get("variant_a")
        return normalize_radio_tuning(variant)

    async def get_global_top(
        self, limit: int = _GLOBAL_TOP_SIZE
    ) -> list[Track]:
        redis = get_redis_client()
        key = f"rec:global_top:{limit}"
        cached = await redis.get(key)
        if cached:
            return await self._rec_repo.get_tracks_by_ids(json.loads(cached))
        tracks = await self._rec_repo.get_popular_tracks(limit=limit)
        await redis.setex(
            key,
            _midnight_ttl(),
            json.dumps([t.id for t in tracks]),
        )
        return tracks

    async def get_daily_playlist(self, user_id: int) -> dict[str, Any]:
        redis = get_redis_client()
        key = f"rec:daily:{user_id}"
        cached = await redis.get(key)
        if cached:
            cached_payload = _loads_dict_payload(cached)
            if cached_payload is not None:
                return cached_payload

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(user_id)
        history = await self._build_listen_history(user_id)
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
            t for t in unseen if t.id not in {c.id for c in candidates}
        ]
        features = await self._tracks_to_features(all_tracks)
        feat_by_id = {f.track_id: f for f in features}
        cand_features = [feat_by_id[t.id] for t in candidates]
        unseen_features = [
            feat_by_id[t.id] for t in unseen if t.id in feat_by_id
        ]
        rerank_enabled, rerank_lambda = await self._load_diversity_rerank(
            user_id=user_id
        )
        scored = build_daily_mix(
            user_prefs,
            history,
            cand_features,
            _DAILY_SIZE,
            novelty_target=_DAILY_NOVELTY_TARGET,
            unseen_candidates=unseen_features,
            use_diversity_rerank=rerank_enabled,
            diversity_lambda=rerank_lambda,
        )

        from app.services.external_discovery_service import (
            ExternalDiscoveryService,
        )

        external: list[ExternalTrackCandidate] = []
        try:
            async with asyncio.timeout(_EXTERNAL_DISCOVERY_TIMEOUT):
                external = await ExternalDiscoveryService(
                    self._session
                ).discover(
                    user_prefs.preferred_genres,
                    language_affinity=user_prefs.language_affinity,
                    user_locale=user_locale,
                )
        except TimeoutError:
            logger.warning("daily_playlist_external_timeout")

        int_scored, ext_picked = merge_hybrid_playlist(
            scored, external, _DAILY_SIZE
        )
        track_map = {t.id: t for t in all_tracks}
        internal_ids = [
            s.track_id for s in int_scored if s.track_id in track_map
        ]
        global_top = await self.get_global_top()
        if not internal_ids:
            fallback = await self._cold_start_fallback_tracks(size=_DAILY_SIZE)
            internal_ids = [t.id for t in fallback]
        external_track_ids: list[int] = []
        if ext_picked:
            try:
                async with asyncio.timeout(_EXTERNAL_IMPORT_TIMEOUT):
                    external_track_ids = (
                        await self._import_external_candidates(
                            ext_picked, user_id
                        )
                    )
            except TimeoutError:
                logger.warning("daily_playlist_import_timeout")
        await self._telemetry.record_impressions(
            user_id=user_id,
            surface="daily_playlist",
            track_ids=internal_ids + external_track_ids,
        )

        ttl = _midnight_ttl()
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "internal_track_ids": internal_ids,
            "external_track_ids": external_track_ids,
            "global_top_ids": [t.id for t in global_top],
            "generated_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
        }
        if internal_ids or external_track_ids or payload["global_top_ids"]:
            await redis.setex(key, ttl, json.dumps(payload))
        return payload

    async def get_weekly_playlist(self, user_id: int) -> dict[str, Any]:
        redis = get_redis_client()
        key = f"rec:weekly:{user_id}"
        cached = await redis.get(key)
        if cached:
            cached_payload = _loads_dict_payload(cached)
            if cached_payload is not None:
                return cached_payload

        (
            user_prefs,
            user_locale,
        ) = await self._build_user_prefs(user_id)
        history = await self._build_listen_history(user_id)
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
            t for t in unseen if t.id not in {c.id for c in candidates}
        ]
        features = await self._tracks_to_features(all_tracks)
        feat_by_id = {f.track_id: f for f in features}
        cand_features = [feat_by_id[t.id] for t in candidates]
        unseen_features = [
            feat_by_id[t.id] for t in unseen if t.id in feat_by_id
        ]
        scored = build_weekly_mix(
            user_prefs,
            history,
            cand_features,
            _WEEKLY_SIZE,
            novelty_target=_WEEKLY_NOVELTY_TARGET,
            unseen_candidates=unseen_features,
        )

        from app.services.external_discovery_service import (
            ExternalDiscoveryService,
        )

        external: list[ExternalTrackCandidate] = []
        try:
            async with asyncio.timeout(_EXTERNAL_DISCOVERY_TIMEOUT):
                external = await ExternalDiscoveryService(
                    self._session
                ).discover(
                    user_prefs.preferred_genres,
                    limit_per_source=20,
                    language_affinity=user_prefs.language_affinity,
                    user_locale=user_locale,
                )
        except TimeoutError:
            logger.warning("weekly_playlist_external_timeout")

        int_scored, ext_picked = merge_hybrid_playlist(
            scored,
            external,
            _WEEKLY_SIZE,
        )
        track_map = {t.id: t for t in all_tracks}
        internal_ids = [
            s.track_id for s in int_scored if s.track_id in track_map
        ]
        external_track_ids: list[int] = []
        if ext_picked:
            try:
                async with asyncio.timeout(_EXTERNAL_IMPORT_TIMEOUT):
                    external_track_ids = (
                        await self._import_external_candidates(
                            ext_picked, user_id
                        )
                    )
            except TimeoutError:
                logger.warning("weekly_playlist_import_timeout")
        if not internal_ids and not external_track_ids:
            fallback = await self._cold_start_fallback_tracks(
                size=_WEEKLY_SIZE
            )
            internal_ids = [t.id for t in fallback]
        await self._telemetry.record_impressions(
            user_id=user_id,
            surface="weekly_playlist",
            track_ids=internal_ids + external_track_ids,
        )

        ttl = _weekly_ttl()
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "internal_track_ids": internal_ids,
            "external_track_ids": external_track_ids,
            "generated_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
        }
        if internal_ids or external_track_ids:
            await redis.setex(key, ttl, json.dumps(payload))
        return payload

    async def refresh_daily_playlist(self, user_id: int) -> dict[str, Any]:
        redis = get_redis_client()
        await redis.delete(f"rec:daily:{user_id}")
        await redis.delete(f"rec:global_top:{_GLOBAL_TOP_SIZE}")
        return await self.get_daily_playlist(user_id)
