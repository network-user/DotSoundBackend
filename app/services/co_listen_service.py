from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from dotsound_private_core.services import colisten_policy
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.co_listen import CoListenRoom
from app.models.user import User
from app.repositories.co_listen import CoListenRepository
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_CHANNEL = "colisten:room:{}"


class CoListenService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._rooms = CoListenRepository(session)
        self._tracks = TrackRepository(session)

    async def create_room(
        self, user: User, track_id: int
    ) -> CoListenRoom:
        t = await self._tracks.get_by_id(track_id)
        if not t or not t.is_active or not t.is_public:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        r = get_redis_client()
        k = f"colisten:create:{user.id}"
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, 3600)
        if n > colisten_policy.COLISTEN_MAX_ROOMS_PER_USER_PER_HOUR:
            await r.decr(k)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="room_rate_limited",
            )
        rid = uuid.uuid4()
        ex = datetime.now(UTC) + timedelta(
            seconds=colisten_policy.COLISTEN_ROOM_TTL_SECONDS
        )
        room = await self._rooms.create(
            rid, int(user.id), track_id, ex
        )
        await self._session.commit()
        await self._session.refresh(room)
        await self._broadcast(room)
        return room

    async def get_room(self, room_id: uuid.UUID) -> CoListenRoom:
        room = await self._rooms.get(room_id)
        if not room:
            raise HTTPException(404, "not_found")
        if room.expires_at < datetime.now(UTC):
            raise HTTPException(404, "expired")
        return room

    async def patch_state(
        self,
        room_id: uuid.UUID,
        user: User,
        position_ms: int | None = None,
        is_playing: bool | None = None,
        track_id: int | None = None,
    ) -> CoListenRoom:
        room = await self.get_room(room_id)
        can_control = int(user.id) == int(
            room.host_id
        ) or (
            room.dj_id is not None
            and int(user.id) == int(room.dj_id)
        )
        if not can_control:
            raise HTTPException(403, "not_dj")
        if position_ms is not None:
            room.position_ms = max(0, int(position_ms))
        if is_playing is not None:
            room.is_playing = is_playing
        if track_id is not None:
            t2 = await self._tracks.get_by_id(track_id)
            if not t2 or not t2.is_active or not t2.is_public:
                raise HTTPException(404, "Track not found")
            room.track_id = track_id
        room.epoch = int(room.epoch) + 1
        await self._session.commit()
        await self._session.refresh(room)
        await self._broadcast(room)
        return room

    async def _broadcast(self, room: CoListenRoom) -> None:
        d = {
            "room_id": str(room.id),
            "track_id": room.track_id,
            "position_ms": room.position_ms,
            "is_playing": room.is_playing,
            "epoch": room.epoch,
        }
        ch = _CHANNEL.format(room.id)
        r = get_redis_client()
        try:
            await r.publish(
                ch,
                json.dumps(d, ensure_ascii=False),
            )
        except Exception as exc:
            logger.warning("colisten_publish_failed", err=str(exc))
