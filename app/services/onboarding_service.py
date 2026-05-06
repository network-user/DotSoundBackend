from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.user import User
from app.models.user_preference import UserPreference
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.artist import ArtistRepository
from app.repositories.preference import (
    PreferenceRepository,
)
from app.repositories.track import TrackRepository
from app.schemas.onboarding import OnboardingStatusResponse
from app.services.telegram_profile_preflight import (
    preflight_telegram_profile_music,
)

logger = structlog.get_logger(__name__)
_SMART_SKIP_FLAG = "onboarding.smart_skip_enabled"
_ACTIVATION_COUNTER_PREFIX = "activation:counters:"
_ACTIVATION_USERS_PREFIX = "activation:users:"
_ACTIVATION_RETENTION_SECONDS = 35 * 24 * 60 * 60


class OnboardingService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._pref_repo = PreferenceRepository(
            session
        )
        self._artist_repo = ArtistRepository(
            session
        )
        self._track_repo = TrackRepository(session)
        self._session = session
        self._settings_repo = AppSettingsRepository(session)

    async def get_status(
        self, user_id: int
    ) -> UserPreference | None:
        return await self._pref_repo.get_by_user_id(
            user_id
        )

    async def get_status_response(
        self, user: User
    ) -> OnboardingStatusResponse:
        pref = await self._pref_repo.get_by_user_id(
            user.id
        )
        pf = await preflight_telegram_profile_music(user)
        if not pref:
            return OnboardingStatusResponse(
                onboarding_completed=False,
                calibration_completed=False,
                import_prompt_acknowledged=False,
                can_import_from_telegram=(
                    pf.can_import_from_telegram
                ),
                has_telegram_profile_music=(
                    pf.has_telegram_profile_music
                ),
            )
        return OnboardingStatusResponse(
            onboarding_completed=pref.onboarding_completed,
            calibration_completed=pref.calibration_completed,
            preferred_genres=pref.preferred_genres,
            preferred_moods=pref.preferred_moods,
            import_prompt_acknowledged=(
                pref.onboarding_import_acknowledged
            ),
            can_import_from_telegram=(
                pf.can_import_from_telegram
            ),
            has_telegram_profile_music=(
                pf.has_telegram_profile_music
            ),
        )

    async def acknowledge_import_prompt(
        self, user_id: int
    ) -> UserPreference:
        pref = await self._pref_repo.upsert(
            user_id=user_id,
            onboarding_import_acknowledged=True,
        )
        logger.info(
            "onboarding_import_acknowledged",
            user_id=user_id,
        )
        return pref

    async def reset_onboarding_state(
        self, user_id: int
    ) -> UserPreference:
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
            preferred_artist_ids=(
                artist_ids or None
            ),
            preferred_moods=moods or None,
            onboarding_completed=True,
        )
        if artist_ids:
            from app.services.artist_follow_service import (
                ArtistFollowService,
            )

            follow_svc = ArtistFollowService(
                self._session
            )
            await follow_svc.follow_artists_bulk(
                user_id, artist_ids
            )
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
        count: int = 5,
    ) -> list:
        pref = await self._pref_repo.get_by_user_id(
            user_id
        )
        genres = (
            pref.preferred_genres
            if pref and pref.preferred_genres
            else None
        )

        from sqlalchemy import func, select

        from app.models.track import Track

        q = select(Track).where(
            Track.is_active.is_(True),
            Track.is_public.is_(True),
        )
        if genres:
            q = q.where(Track.genre.in_(genres))
        q = q.order_by(
            func.random()
        ).limit(count)

        result = await self._session.execute(q)
        tracks = list(result.scalars().all())

        if len(tracks) < count:
            fallback = await self._session.execute(
                select(Track)
                .where(
                    Track.is_active.is_(True),
                    Track.is_public.is_(True),
                )
                .order_by(Track.play_count.desc())
                .limit(count)
            )
            seen = {t.id for t in tracks}
            for t in fallback.scalars().all():
                if t.id not in seen:
                    tracks.append(t)
                    seen.add(t.id)
                if len(tracks) >= count:
                    break

        return tracks

    async def save_calibration(
        self,
        user_id: int,
        items: list[dict],
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
        dislike_repo = DislikeRepository(
            self._session
        )

        for item in items:
            track_id = item["track_id"]
            liked = item["liked"]
            if liked is None:
                continue
            if liked:
                existing = await like_repo.get(
                    user_id, track_id
                )
                if not existing:
                    await like_repo.add(
                        user_id, track_id
                    )
            else:
                existing = await dislike_repo.get(
                    user_id, track_id
                )
                if not existing:
                    await dislike_repo.add(
                        user_id, track_id
                    )

        logger.info(
            "onboarding_calibration_saved",
            user_id=user_id,
            count=len(items),
        )
        return pref

    async def is_smart_skip_enabled(self) -> bool:
        return await self._settings_repo.get_feature_flag(
            _SMART_SKIP_FLAG,
            default=True,
        )

    async def complete(
        self, user_id: int
    ) -> UserPreference:
        return await self._pref_repo.upsert(
            user_id=user_id,
            onboarding_completed=True,
            onboarding_import_acknowledged=True,
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
        existing = await self._pref_repo.get_by_user_id(
            user_id
        )
        if (
            existing
            and existing.preferred_genres
            and len(existing.preferred_genres) >= 3
        ):
            return {
                "genres": list(
                    existing.preferred_genres
                ),
                "artist_ids": list(
                    existing.preferred_artist_ids
                    or []
                ),
                "moods": list(
                    existing.preferred_moods or []
                ),
            }

        all_genres = (
            await self.get_available_genres()
        )
        default_genres = list(all_genres[:5])

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
        )
        return {
            "genres": default_genres,
            "artist_ids": [],
            "moods": [],
        }

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
        if event == "auth_success":
            if pref.auth_first_seen_at is None:
                pref.auth_first_seen_at = now
                await self._session.flush()
        elif event in ("home_first_play", "home_first_session_start"):
            if pref.first_play_at is None:
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
            step_key = (
                f"{_ACTIVATION_USERS_PREFIX}{day}:{event}:step:{step}"
            )
            pipe.sadd(step_key, str(user_id))
            pipe.expire(step_key, _ACTIVATION_RETENTION_SECONDS)
        await pipe.execute()

    async def get_available_genres(
        self,
    ) -> list[str]:
        db_genres = (
            await self._track_repo.get_unique_genres()
        )
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
    ) -> list:
        return await self._artist_repo.list_popular(
            limit=limit,
            genre_filter=genres,
        )
