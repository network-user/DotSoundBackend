from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from dotsound_private_core.services import playlist_collab_policy
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.playlist import PlaylistRepository
from app.repositories.playlist_collab import (
    InviteTokenRepository,
    PlaylistCollabRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _h(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PlaylistCollabService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._playlists = PlaylistRepository(session)
        self._cr = PlaylistCollabRepository(session)
        self._inv = InviteTokenRepository(session)

    async def create_invite(
        self,
        playlist_id: int,
        owner: User,
        target_role: str = "editor",
    ) -> tuple[str, datetime]:
        pl = await self._playlists.get_by_id(playlist_id)
        if not pl or int(pl.owner_id) != int(owner.id):
            raise HTTPException(403, "not_owner")
        n = await self._cr.count_by_playlist(playlist_id)
        if n + 1 >= playlist_collab_policy.PLAYLIST_MAX_COLLABORATORS:
            raise HTTPException(400, "collab_cap")
        raw = secrets.token_urlsafe(32)
        exp = datetime.now(UTC) + timedelta(
            hours=playlist_collab_policy.PLAYLIST_INVITE_TTL_HOURS
        )
        await self._inv.insert(
            _h(raw), playlist_id, int(owner.id), target_role, exp
        )
        await self._session.commit()
        return raw, exp

    async def accept(
        self, token: str, user: User
    ) -> int:
        row = await self._inv.by_hash(_h(token))
        if not row or row.expires_at < datetime.now(UTC):
            raise HTTPException(404, "invalid_invite")
        uids = await self._cr.list_user_ids(
            int(row.playlist_id)
        )
        if int(user.id) in uids:
            raise HTTPException(400, "already_collaborator")
        await self._cr.add(
            int(row.playlist_id), int(user.id), row.target_role
        )
        await self._inv.delete_by_id(int(row.id))
        await self._session.commit()
        return int(row.playlist_id)
