from __future__ import annotations

import structlog
from dotsound_private_core.services.snippet_policy import (
    SNIPPET_DAILY_PER_USER_CAP,
    normalize_snippet_bounds,
)
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import config as _cfg
from app.core.redis import get_redis_client
from app.models.track_snippet import TrackSnippet
from app.models.user import User
from app.repositories.track import TrackRepository
from app.services.snippet_worker import transcode_snippet_task

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class SnippetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tracks = TrackRepository(session)

    async def request_snippet(
        self,
        track_id: int,
        user: User,
        start_ms: int,
        end_ms: int,
    ) -> TrackSnippet:
        t = await self._tracks.get_by_id(track_id)
        if not t or not t.is_active:
            raise HTTPException(404, "not_found")
        b = normalize_snippet_bounds(int(start_ms), int(end_ms))
        if b is None:
            raise HTTPException(400, "invalid_bounds")
        r = get_redis_client()
        k = f"snippet:day:{user.id}"
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, 86400)
        if n > SNIPPET_DAILY_PER_USER_CAP:
            await r.decr(k)
            raise HTTPException(429, "snippet_cap")
        sn = TrackSnippet(
            track_id=track_id,
            user_id=int(user.id),
            file_key=None,
            start_ms=b[0],
            end_ms=b[1],
            status="pending",
        )
        self._session.add(sn)
        await self._session.flush()
        await self._session.refresh(sn)
        if not _cfg.settings.snippet_ffmpeg_enabled:
            sn.status = "disabled"
        await self._session.commit()
        await self._session.refresh(sn)
        if _cfg.settings.snippet_ffmpeg_enabled:
            await transcode_snippet_task.kiq(int(sn.id))
        return sn
