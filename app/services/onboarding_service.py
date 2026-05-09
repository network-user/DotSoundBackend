from datetime import UTC, datetime
from typing import Any

import structlog
from dotsound_private_core.services.onboarding_policy import (
    DEFAULT_DISPLAY_NAME,
    GENRE_BUBBLE_COUNT,
    TASTE_SWIPE_TRACK_COUNT,
    TasteSwipeConfig,
    TasteTrackInput,
    derive_default_display_name,
    has_minimum_taste_signal,
    is_display_name_valid,
    order_taste_swipe_tracks,
    pick_default_genres_for_locale,
    should_offer_import_in_onboarding,
    trim_genre_bubbles,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.redis import get_redis_client
from app.models.track import Track
from app.models.user import User
from app.models.user_preference import UserPreference
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.artist import ArtistRepository
from app.repositories.preference import (
    PreferenceRepository,
)
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.schemas.onboarding import (
    GenreBubbleResponse,
    OnboardingBootstrapResponse,
    OnboardingProfileSubmitResponse,
    OnboardingStatusResponse,
    ProfileDefaultsResponse,
    TasteSwipeDecision,
)
from app.services.telegram_profile_preflight import (
    preflight_telegram_profile_music,
)

logger = structlog.get_logger(__name__)
_SMART_SKIP_FLAG = "onboarding.smart_skip_enabled"
_ACTIVATION_COUNTER_PREFIX = "activation:counters:"
_ACTIVATION_USERS_PREFIX = "activation:users:"
_ACTIVATION_RETENTION_SECONDS = 35 * 24 * 60 * 60
_DICEBEAR_IDENTICON = "https://api.dicebear.com/9.x/identicon/svg?seed={seed}"
_TASTE_CANDIDATE_MULTIPLIER = 4


class OnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._pref_repo = PreferenceRepository(session)
        self._artist_repo = ArtistRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._session = session
        self._settings_repo = AppSettingsRepository(session)

    async def get_status(self, user_id: int) -> UserPreference | None:
        return await self._pref_repo.get_by_user_id(user_id)

    async def get_status_response(
        self, user: User
    ) -> OnboardingStatusResponse:
        pref = await self._pref_repo.get_by_user_id(user.id)
        pf = await preflight_telegram_profile_music(user)
        profile_completed = self._is_profile_completed(user)
        if not pref:
            return OnboardingStatusResponse(
                onboarding_completed=False,
                calibration_completed=False,
                import_prompt_acknowledged=False,
                can_import_from_telegram=(pf.can_import_from_telegram),
                has_telegram_profile_music=(pf.has_telegram_profile_music),
                profile_completed=profile_completed,
            )
        return OnboardingStatusResponse(
            onboarding_completed=pref.onboarding_completed,
            calibration_completed=pref.calibration_completed,
            preferred_genres=pref.preferred_genres,
            preferred_moods=pref.preferred_moods,
            import_prompt_acknowledged=(pref.onboarding_import_acknowledged),
            can_import_from_telegram=(pf.can_import_from_telegram),
            has_telegram_profile_music=(pf.has_telegram_profile_music),
            profile_completed=profile_completed,
            legal_accepted_version=pref.legal_accepted_version,
            is_adult_confirmed=pref.is_adult_confirmed,
        )

    async def acknowledge_import_prompt(self, user_id: int) -> UserPreference:
        pref = await self._pref_repo.upsert(
            user_id=user_id,
            onboarding_import_acknowledged=True,
        )
        logger.info(
            "onboarding_import_acknowledged",
            user_id=user_id,
        )
        return pref

    async def reset_onboarding_state(self, user_id: int) -> UserPreference:
        """Debug / QA: show onboarding wizard again from a clean state."""
        pref = await self._pref_repo.upsert(
            user_id=user_id,
            onboarding_completed=False,
            calibration_completed=False,
            onboarding_import_acknowledged=False,
            preferred_genres=None,
            preferred_artist_ids=None,
            preferred_moods=None,
        )
        logger.info(
            "onboarding_state_reset",
            user_id=user_id,
        )
        return pref

    async def save_preferences(
        self,
        user_id: int,
        genres: list[str],
        artist_ids: list[int],
        moods: list[str],
    ) -> UserPreference:
        pref = await self._pref_repo.upsert(
            user_id=user_id,
            preferred_genres=genres or None,
            preferred_artist_ids=(artist_ids or None),
            preferred_moods=moods or None,
            onboarding_completed=True,
        )
        if artist_ids:
            from app.services.artist_follow_service import (
                ArtistFollowService,
            )

            follow_svc = ArtistFollowService(self._session)
            await follow_svc.follow_artists_bulk(user_id, artist_ids)
        logger.info(
            "onboarding_preferences_saved",
            user_id=user_id,
            genres=genres,
            moods=moods,
        )
        return pref

    async def get_calibration_tracks(
        self,
        user_id: int,
        count: int = TASTE_SWIPE_TRACK_COUNT,
    ) -> list[Track]:
        """Pick a small list of tracks for the swipe step.

        Wraps :func:`order_taste_swipe_tracks` from PrivateCore so
        the chosen tracks rotate genre and respect the user locale.
        """
        pref = await self._pref_repo.get_by_user_id(user_id)
        user = await self._user_repo.get_by_id(user_id)
        locale = user.locale if user else None
        genres = (
            pref.preferred_genres if pref and pref.preferred_genres else None
        )

        candidate_count = max(
            count * _TASTE_CANDIDATE_MULTIPLIER,
            count + 5,
        )

        q = select(Track).where(
            Track.is_active.is_(True),
            Track.is_public.is_(True),
            TrackRepository._playback_listing_allowed(),
        )
        if genres:
            q = q.where(Track.genre.in_(genres))
        q = q.order_by(func.random()).limit(candidate_count)

        result = await self._session.execute(q)
        candidates = list(result.scalars().all())

        if len(candidates) < candidate_count:
            fallback = await self._session.execute(
                select(Track)
                .where(
                    Track.is_active.is_(True),
                    Track.is_public.is_(True),
                    TrackRepository._playback_listing_allowed(),
                )
                .order_by(Track.play_count.desc())
                .limit(candidate_count)
            )
            seen = {t.id for t in candidates}
            for t in fallback.scalars().all():
                if t.id not in seen:
                    candidates.append(t)
                    seen.add(t.id)
                if len(candidates) >= candidate_count:
                    break

        if not candidates:
            return []

        inputs = [
            TasteTrackInput(
                track_id=t.id,
                genre=t.genre,
                title=t.title,
                artist=t.artist,
                play_count=int(t.play_count or 0),
            )
            for t in candidates
        ]
        ordered_ids = order_taste_swipe_tracks(
            inputs,
            locale=locale,
            selected_genres=tuple(genres) if genres else None,
            config=TasteSwipeConfig(max_count=count),
        )
        by_id = {t.id: t for t in candidates}
        return [by_id[i] for i in ordered_ids if i in by_id]

    async def save_calibration(
        self,
        user_id: int,
        items: list[dict[str, Any]],
    ) -> UserPreference:
        pref = await self._pref_repo.upsert(
            user_id=user_id,
            calibration_completed=True,
        )
        from app.repositories.dislike import (
            DislikeRepository,
        )
        from app.repositories.like import (
            LikeRepository,
        )

        like_repo = LikeRepository(self._session)
        dislike_repo = DislikeRepository(self._session)

        for item in items:
            track_id = item["track_id"]
            liked = item["liked"]
            if liked is None:
                continue
            if liked:
                like = await like_repo.get(user_id, track_id)
                if not like:
                    await like_repo.add(user_id, track_id)
            else:
                dislike = await dislike_repo.get(user_id, track_id)
                if not dislike:
                    await dislike_repo.add(user_id, track_id)

        logger.info(
            "onboarding_calibration_saved",
            user_id=user_id,
            count=len(items),
        )
        return pref

    async def save_taste_swipe_batch(
        self,
        user_id: int,
        decisions: list[TasteSwipeDecision],
    ) -> int:
        """Persist a batch of swipe decisions atomically.

        Returns how many decisions resulted in a like/dislike row.
        """
        if not decisions:
            return 0
        from app.repositories.dislike import (
            DislikeRepository,
        )
        from app.repositories.like import (
            LikeRepository,
        )

        like_repo = LikeRepository(self._session)
        dislike_repo = DislikeRepository(self._session)
        saved = 0
        for d in decisions:
            if d.decision == "like":
                like = await like_repo.get(user_id, d.track_id)
                if not like:
                    await like_repo.add(user_id, d.track_id)
                saved += 1
            elif d.decision == "dislike":
                dislike = await dislike_repo.get(user_id, d.track_id)
                if not dislike:
                    await dislike_repo.add(user_id, d.track_id)
                saved += 1

        await self._pref_repo.upsert(
            user_id=user_id,
            calibration_completed=True,
        )
        logger.info(
            "onboarding_taste_swipe_saved",
            user_id=user_id,
            count=len(decisions),
            saved=saved,
        )
        return saved

    async def is_smart_skip_enabled(self) -> bool:
        return await self._settings_repo.get_feature_flag(
            _SMART_SKIP_FLAG,
            default=True,
        )

    async def complete(
        self,
        user_id: int,
        legal_accepted_version: str | None = None,
    ) -> UserPreference:
        """Mark onboarding as done and, if the client provided the
        version of the legal pack it displayed, record the implicit
        acceptance + adult confirmation. The disclosure shown under
        the final "Готово" button states 18+ and "Условия + Privacy",
        so a single tap registers all three at once.
        """
        kwargs: dict[str, Any] = {
            "onboarding_completed": True,
            "onboarding_import_acknowledged": True,
        }
        if legal_accepted_version:
            now = datetime.now(UTC)
            kwargs["legal_accepted_version"] = legal_accepted_version
            kwargs["legal_accepted_at"] = now
            kwargs["is_adult_confirmed"] = True
            kwargs["adult_confirmed_at"] = now
        return await self._pref_repo.upsert(
            user_id=user_id,
            **kwargs,
        )

    async def apply_smart_default_profile(
        self, user_id: int
    ) -> dict[str, list[Any]]:
        if not await self.is_smart_skip_enabled():
            await self.complete(user_id)
            logger.info(
                "onboarding_smart_skip_disabled",
                user_id=user_id,
                flag=_SMART_SKIP_FLAG,
            )
            return {
                "genres": [],
                "artist_ids": [],
                "moods": [],
            }
        existing = await self._pref_repo.get_by_user_id(user_id)
        if (
            existing
            and existing.preferred_genres
            and len(existing.preferred_genres) >= 3
        ):
            return {
                "genres": list(existing.preferred_genres),
                "artist_ids": list(existing.preferred_artist_ids or []),
                "moods": list(existing.preferred_moods or []),
            }

        user = await self._user_repo.get_by_id(user_id)
        locale = user.locale if user else None
        all_genres = await self.get_available_genres()
        default_genres = pick_default_genres_for_locale(
            locale,
            all_genres,
            count=5,
        )

        await self._pref_repo.upsert(
            user_id=user_id,
            preferred_genres=default_genres or None,
            onboarding_completed=True,
            onboarding_import_acknowledged=True,
        )
        logger.info(
            "onboarding_smart_skip_applied",
            user_id=user_id,
            applied_genres=default_genres,
            locale=locale,
        )
        return {
            "genres": default_genres,
            "artist_ids": [],
            "moods": [],
        }

    async def get_profile_defaults(
        self, user: User
    ) -> ProfileDefaultsResponse:
        suggested_name = derive_default_display_name(
            telegram_first_name=(
                user.first_name if user.auth_provider == "telegram" else None
            ),
            telegram_username=(
                user.username if user.auth_provider == "telegram" else None
            ),
            email=(user.email if user.auth_provider == "email" else None),
        )
        if not suggested_name or suggested_name == DEFAULT_DISPLAY_NAME:
            suggested_name = (
                user.display_name or user.first_name or DEFAULT_DISPLAY_NAME
            )
        if user.display_name:
            suggested_name = user.display_name

        avatar_url: str | None = None
        if user.avatar_key:
            try:
                avatar_url = await s3.get_presigned_url(user.avatar_key)
            except Exception as exc:
                logger.warning(
                    "avatar_presign_failed",
                    user_id=user.id,
                    error=str(exc),
                )
        if not avatar_url:
            seed = user.avatar_seed or str(user.telegram_id or user.id)
            avatar_url = _DICEBEAR_IDENTICON.format(seed=seed)

        initials = _compute_initials(suggested_name)
        return ProfileDefaultsResponse(
            suggested_display_name=suggested_name,
            current_display_name=user.display_name,
            suggested_avatar_url=avatar_url,
            has_custom_avatar=bool(user.avatar_key),
            auth_provider=user.auth_provider,
            suggested_initials=initials,
            locale=user.locale,
        )

    async def save_profile(
        self,
        user: User,
        *,
        display_name: str | None,
        locale: str | None,
        use_default_avatar: bool,
    ) -> OnboardingProfileSubmitResponse:
        from app.services.user_service import UserService

        user_service = UserService(self._session)
        applied_name = display_name
        if applied_name is not None:
            cleaned = applied_name.strip()
            if not is_display_name_valid(cleaned):
                applied_name = None
            else:
                applied_name = cleaned

        if applied_name and applied_name != user.display_name:
            await user_service.update_display_name(user.id, applied_name)

        if locale and locale != user.locale:
            user.locale = locale
            await self._session.flush()
            await self._session.refresh(user)

        if use_default_avatar and user.avatar_key:
            user.avatar_key = None
            await self._session.flush()
            await self._session.refresh(user)

        avatar_url: str | None = None
        if user.avatar_key:
            try:
                avatar_url = await s3.get_presigned_url(user.avatar_key)
            except Exception as exc:
                logger.warning(
                    "avatar_presign_failed",
                    user_id=user.id,
                    error=str(exc),
                )
        if not avatar_url:
            seed = user.avatar_seed or str(user.telegram_id or user.id)
            avatar_url = _DICEBEAR_IDENTICON.format(seed=seed)

        final_name = (
            user.display_name
            or applied_name
            or user.first_name
            or DEFAULT_DISPLAY_NAME
        )
        profile_completed = self._is_profile_completed(user)
        logger.info(
            "onboarding_profile_saved",
            user_id=user.id,
            has_custom_name=bool(user.display_name),
            locale=user.locale,
        )
        return OnboardingProfileSubmitResponse(
            display_name=final_name,
            avatar_url=avatar_url,
            profile_completed=profile_completed,
        )

    async def bootstrap(self, user: User) -> OnboardingBootstrapResponse:
        status = await self.get_status_response(user)
        defaults = await self.get_profile_defaults(user)
        bubbles = await self.get_genre_bubbles(
            user.locale,
        )
        show_import = should_offer_import_in_onboarding(
            can_import_from_telegram=(status.can_import_from_telegram),
            has_telegram_profile_music=(status.has_telegram_profile_music),
            already_acknowledged=(status.import_prompt_acknowledged),
        )
        return OnboardingBootstrapResponse(
            status=status,
            profile_defaults=defaults,
            genre_bubbles=bubbles,
            show_import_offer=show_import,
        )

    async def get_genre_bubbles(
        self,
        locale: str | None,
        cap: int = GENRE_BUBBLE_COUNT,
    ) -> list[GenreBubbleResponse]:
        all_genres = await self.get_available_genres()
        trimmed = trim_genre_bubbles(
            all_genres,
            locale,
            cap=cap,
        )
        if not trimmed:
            return []

        cover_query = (
            select(
                Track.genre,
                Track.cover_key,
                func.count(Track.id)
                .over(partition_by=Track.genre)
                .label("genre_count"),
            )
            .where(
                Track.is_active.is_(True),
                Track.is_public.is_(True),
                TrackRepository._playback_listing_allowed(),
                Track.cover_key.is_not(None),
                Track.genre.in_(trimmed),
            )
            .order_by(
                Track.genre,
                Track.play_count.desc().nullslast(),
            )
        )

        result = await self._session.execute(cover_query)
        covers_by_genre: dict[str, list[str]] = {}
        counts_by_genre: dict[str, int] = {}
        for genre, cover_key, count in result.all():
            if genre is None or cover_key is None:
                continue
            covers_by_genre.setdefault(genre, [])
            counts_by_genre[genre] = int(count)
            if len(covers_by_genre[genre]) < 3:
                covers_by_genre[genre].append(cover_key)

        return [
            GenreBubbleResponse(
                genre=g,
                track_count=counts_by_genre.get(g, 0),
                sample_cover_keys=covers_by_genre.get(g, []),
            )
            for g in trimmed
        ]

    async def process_activation_event(
        self,
        *,
        user_id: int,
        event: str,
        meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        pref = await self._pref_repo.get_by_user_id(user_id)
        if pref is None:
            pref = await self._pref_repo.upsert(user_id=user_id)

        out_meta: dict[str, Any] = dict(meta or {})
        if event == "auth_success" and pref.auth_first_seen_at is None:
            pref.auth_first_seen_at = now
            await self._session.flush()
        elif (
            event in ("home_first_play", "home_first_session_start")
            and pref.first_play_at is None
        ):
            pref.first_play_at = now
            if pref.auth_first_seen_at is not None:
                delta = now - pref.auth_first_seen_at
                out_meta["ms_from_auth_server"] = int(
                    delta.total_seconds() * 1000
                )
            await self._session.flush()

        await self._record_activation_aggregate(
            user_id=user_id,
            event=event,
            meta=out_meta,
            now=now,
        )
        return out_meta

    async def _record_activation_aggregate(
        self,
        *,
        user_id: int,
        event: str,
        meta: dict[str, Any],
        now: datetime,
    ) -> None:
        day = now.strftime("%Y%m%d")
        redis = get_redis_client()
        counter_key = f"{_ACTIVATION_COUNTER_PREFIX}{day}"
        users_key = f"{_ACTIVATION_USERS_PREFIX}{day}:{event}"

        pipe = redis.pipeline()
        pipe.hincrby(counter_key, event, 1)
        pipe.expire(counter_key, _ACTIVATION_RETENTION_SECONDS)
        pipe.sadd(users_key, str(user_id))
        pipe.expire(users_key, _ACTIVATION_RETENTION_SECONDS)

        step = meta.get("step")
        if isinstance(step, str) and step:
            step_key = f"{_ACTIVATION_USERS_PREFIX}{day}:{event}:step:{step}"
            pipe.sadd(step_key, str(user_id))
            pipe.expire(step_key, _ACTIVATION_RETENTION_SECONDS)
        await pipe.execute()

    async def get_available_genres(
        self,
    ) -> list[str]:
        db_genres = await self._track_repo.get_unique_genres()
        default_genres = [
            "hip-hop",
            "pop",
            "rock",
            "electronic",
            "r&b",
            "jazz",
            "classical",
            "indie",
            "metal",
            "folk",
            "latin",
            "country",
            "blues",
            "soul",
            "reggae",
            "punk",
            "ambient",
            "house",
            "techno",
            "trap",
        ]
        seen: set[str] = set()
        result: list[str] = []
        for g in db_genres + default_genres:
            key = g.lower().strip()
            if key and key not in seen:
                seen.add(key)
                result.append(g)
        return result

    async def get_popular_artists(
        self,
        genres: list[str] | None = None,
        limit: int = 50,
    ) -> list[Any]:
        return await self._artist_repo.list_popular(
            limit=limit,
            genre_filter=genres,
        )

    @staticmethod
    def _is_profile_completed(user: User) -> bool:
        if user.display_name and user.display_name.strip():
            return True
        return bool(user.avatar_key)

    def has_minimum_taste(
        self,
        pref: UserPreference | None,
        swipe_decisions: int = 0,
    ) -> bool:
        if pref is None:
            return swipe_decisions >= 1
        return has_minimum_taste_signal(
            selected_genres=pref.preferred_genres,
            selected_artist_ids=pref.preferred_artist_ids,
            swipe_decisions=swipe_decisions,
        )


def _compute_initials(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return ""
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        head = parts[0]
        return head[:2].upper()
    return (parts[0][0] + parts[1][0]).upper()
