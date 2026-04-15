import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preference import UserPreference
from app.repositories.artist import ArtistRepository
from app.repositories.preference import (
    PreferenceRepository,
)
from app.repositories.track import TrackRepository

logger = structlog.get_logger(__name__)


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

    async def get_status(
        self, user_id: int
    ) -> UserPreference | None:
        return await self._pref_repo.get_by_user_id(
            user_id
        )

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

        from app.models.track import Track
        from sqlalchemy import func, select

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
        from app.repositories.like import (
            LikeRepository,
        )
        from app.repositories.dislike import (
            DislikeRepository,
        )

        like_repo = LikeRepository(self._session)
        dislike_repo = DislikeRepository(
            self._session
        )

        for item in items:
            track_id = item["track_id"]
            liked = item["liked"]
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

    async def complete(
        self, user_id: int
    ) -> UserPreference:
        return await self._pref_repo.upsert(
            user_id=user_id,
            onboarding_completed=True,
        )

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
