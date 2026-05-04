import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import (
    ArtistCatalogRepository,
)
from app.repositories.artist_follow import (
    ArtistFollowRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_FULL_SYNC_ENQUEUE_LOCK_PREFIX = "artist:catalog:enqueue:full:"
_RELEASE_ENQUEUE_LOCK_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


class ArtistFollowService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ArtistFollowRepository(session)
        self._artist_repo = ArtistRepository(session)
        self._catalog_repo = ArtistCatalogRepository(
            session
        )

    async def _enqueue_station_sync_if_stale(
        self, artist_id: int
    ) -> None:
        from datetime import UTC, datetime, timedelta

        from app.config import settings
        from app.services.artist_catalog_sync_worker import (
            sync_artist_similar_station_task,
        )

        synced_at = (
            await self._catalog_repo.get_station_synced_at(
                artist_id
            )
        )
        threshold = timedelta(
            days=settings.artist_station_stale_threshold_days
        )
        if (
            synced_at is None
            or datetime.now(UTC) - synced_at > threshold
        ):
            await sync_artist_similar_station_task.kiq(
                artist_id
            )

    async def _try_acquire_full_sync_enqueue_lock(
        self,
        artist_id: int,
        owner_token: str,
        ttl_seconds: int,
    ) -> bool:
        redis = get_redis_client()
        key = f"{_FULL_SYNC_ENQUEUE_LOCK_PREFIX}{artist_id}"
        result = await redis.set(
            key,
            owner_token,
            nx=True,
            ex=int(ttl_seconds),
        )
        return bool(result)

    async def _release_full_sync_enqueue_lock(
        self,
        artist_id: int,
        owner_token: str,
    ) -> None:
        redis = get_redis_client()
        key = f"{_FULL_SYNC_ENQUEUE_LOCK_PREFIX}{artist_id}"
        await redis.eval(
            _RELEASE_ENQUEUE_LOCK_LUA,
            1,
            key,
            owner_token,
        )

    async def _enqueue_full_sync_if_stale(
        self,
        artist_id: int,
    ) -> None:
        from datetime import UTC, datetime, timedelta
        from secrets import token_hex

        from app.config import settings
        from app.services.artist_catalog_sync_worker import (
            sync_artist_catalog_task,
        )

        latest_synced_at = (
            await self._catalog_repo.latest_synced_at_for_artist(
                artist_id
            )
        )
        threshold = timedelta(
            days=settings.artist_catalog_full_sync_stale_threshold_days
        )
        if (
            latest_synced_at is not None
            and datetime.now(UTC) - latest_synced_at <= threshold
        ):
            return

        owner_token = token_hex(16)
        acquired = await self._try_acquire_full_sync_enqueue_lock(
            artist_id,
            owner_token,
            settings.artist_catalog_enqueue_lock_ttl_seconds,
        )
        if not acquired:
            return

        try:
            await sync_artist_catalog_task.kiq(artist_id=artist_id)
        finally:
            await self._release_full_sync_enqueue_lock(
                artist_id,
                owner_token,
            )

    async def toggle_follow(
        self, user_id: int, artist_id: int
    ) -> dict:
        artist = await self._artist_repo.get_by_id(
            artist_id
        )
        if artist is None:
            raise ValueError("artist_not_found")
        following = await self._repo.toggle(
            user_id, artist_id
        )
        follower_count = await self._repo.count_followers(
            artist_id
        )
        if following:
            await self._enqueue_station_sync_if_stale(
                artist_id
            )
            await self._enqueue_full_sync_if_stale(artist_id)
        logger.info(
            "artist_follow_toggled",
            user_id=user_id,
            artist_id=artist_id,
            following=following,
        )
        return {
            "artist_id": artist_id,
            "following": following,
            "follower_count": follower_count,
        }

    async def get_status(
        self, user_id: int, artist_id: int
    ) -> bool:
        return await self._repo.is_following(
            user_id, artist_id
        )

    async def get_follower_count(
        self, artist_id: int
    ) -> int:
        return await self._repo.count_followers(artist_id)

    async def follow_artists_bulk(
        self, user_id: int, artist_ids: list[int]
    ) -> None:
        for artist_id in artist_ids:
            await self._repo.add(user_id, artist_id)
            await self._enqueue_station_sync_if_stale(
                artist_id
            )
            await self._enqueue_full_sync_if_stale(artist_id)
        if artist_ids:
            logger.info(
                "artist_follow_bulk",
                user_id=user_id,
                count=len(artist_ids),
            )
