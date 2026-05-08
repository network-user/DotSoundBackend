import hashlib

import structlog
from dotsound_private_core.services.playcount_policy import (
    qualifies_for_public_playcount,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.repositories.track import (
    TrackRepository,
)
from app.services.search_playcount_drain import (
    mark_playcount_dirty_async,
)

logger = structlog.get_logger(__name__)
_REDIS_DEDUP_TTL = 86400


class PublicPlayCountService:
    def __init__(self, session: AsyncSession) -> None:
        self._track_repo = TrackRepository(session)

    @staticmethod
    def _key_authenticated(user_id: int, track_id: int) -> str:
        return f"pc:u{user_id}:t{track_id}"

    @staticmethod
    def _key_guest(client_ip: str, track_id: int) -> str:
        h = hashlib.sha256(f"{client_ip}".encode()).hexdigest()[:24]
        return f"pc:g{h}:t{track_id}"

    async def bump_after_qualified_listen(
        self,
        user_id: int,
        track_id: int,
        completed: bool,
        skipped: bool,
        duration_listened: int,
    ) -> None:
        if not qualifies_for_public_playcount(
            duration_listened,
            completed,
            skipped,
        ):
            return
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active or not track.is_public:
            return
        k = self._key_authenticated(user_id, track_id)
        if not await self._acquire_dedup_slot(k):
            return
        await self._do_increment(track_id, user_id)

    async def bump_guest_from_play(
        self,
        track_id: int,
        client_ip: str,
    ) -> int | None:
        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active or not track.is_public:
            return None
        if not client_ip.strip():
            return int(track.play_count or 0)
        k = self._key_guest(client_ip, track_id)
        if not await self._acquire_dedup_slot(k):
            r = await self._track_repo.get_by_id(track_id)
            return int(r.play_count or 0) if r else None
        found = await self._track_repo.increment_play_count(track_id)
        if not found:
            return None
        await mark_playcount_dirty_async(track_id)
        logger.info(
            "playcount_bump_guest",
            track_id=track_id,
        )
        t2 = await self._track_repo.get_by_id(track_id)
        return int(t2.play_count or 0) if t2 else 0

    async def _acquire_dedup_slot(self, redis_key: str) -> bool:
        redis = get_redis_client()
        try:
            r = await redis.set(
                redis_key,
                "1",
                ex=_REDIS_DEDUP_TTL,
                nx=True,
            )
            if r:
                return True
        except Exception as exc:
            logger.warning(
                "playcount_dedup_redis",
                err=str(exc),
            )
            return True
        return bool(r)

    async def _do_increment(self, track_id: int, user_id: int) -> None:
        found = await self._track_repo.increment_play_count(track_id)
        if not found:
            return
        await mark_playcount_dirty_async(track_id)
        logger.info(
            "playcount_bump_auth_listen",
            user_id=user_id,
            track_id=track_id,
        )
