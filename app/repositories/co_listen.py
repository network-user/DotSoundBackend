from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.co_listen import CoListenRoom
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class CoListenRepository(
    BaseRepository[CoListenRoom]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CoListenRoom)

    async def get(
        self, room_id: uuid.UUID
    ) -> CoListenRoom | None:
        r = await self._session.execute(
            select(CoListenRoom).where(
                CoListenRoom.id == room_id
            )
        )
        return r.scalar_one_or_none()

    async def create(
        self,
        room_id: uuid.UUID,
        host_id: int,
        track_id: int,
        expires_at: datetime,
    ) -> CoListenRoom:
        room = CoListenRoom(
            id=room_id,
            host_id=host_id,
            dj_id=host_id,
            track_id=track_id,
            position_ms=0,
            is_playing=True,
            epoch=1,
            expires_at=expires_at,
        )
        self._session.add(room)
        await self._session.flush()
        return room
