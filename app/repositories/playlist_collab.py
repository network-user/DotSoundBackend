from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist_collab import (
    PlaylistCollaborator,
    PlaylistInviteToken,
)
from app.models.user import User
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class PlaylistCollabRepository(
    BaseRepository[PlaylistCollaborator]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PlaylistCollaborator)

    async def count_by_playlist(self, playlist_id: int) -> int:
        from sqlalchemy import func

        r = await self._session.execute(
            select(func.count())
            .select_from(PlaylistCollaborator)
            .where(
                PlaylistCollaborator.playlist_id == playlist_id
            )
        )
        return int(r.scalar_one())

    async def add(
        self, playlist_id: int, user_id: int, role: str
    ) -> None:
        self._session.add(
            PlaylistCollaborator(
                playlist_id=playlist_id,
                user_id=user_id,
                role=role,
            )
        )
        await self._session.flush()

    async def list_user_ids(
        self, playlist_id: int
    ) -> list[int]:
        r = await self._session.execute(
            select(PlaylistCollaborator.user_id)
            .where(PlaylistCollaborator.playlist_id == playlist_id)
        )
        return [int(x) for x in r.scalars().all()]

    async def list_with_users(
        self, playlist_id: int
    ) -> list[tuple[PlaylistCollaborator, User]]:
        r = await self._session.execute(
            select(PlaylistCollaborator, User)
            .join(
                User,
                User.id == PlaylistCollaborator.user_id,
            )
            .where(
                PlaylistCollaborator.playlist_id == playlist_id
            )
            .order_by(PlaylistCollaborator.created_at.asc())
        )
        return list(r.all())

    async def remove(
        self, playlist_id: int, user_id: int
    ) -> bool:
        result = await self._session.execute(
            delete(PlaylistCollaborator).where(
                PlaylistCollaborator.playlist_id == playlist_id,
                PlaylistCollaborator.user_id == user_id,
            )
        )
        if result.rowcount > 0:
            await self._session.flush()
            return True
        return False


class InviteTokenRepository(
    BaseRepository[PlaylistInviteToken]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PlaylistInviteToken)

    async def insert(
        self,
        token_hash: str,
        playlist_id: int,
        inviter_id: int,
        target_role: str,
        expires_at: datetime,
    ) -> PlaylistInviteToken:
        row = PlaylistInviteToken(
            token_hash=token_hash,
            playlist_id=playlist_id,
            inviter_id=inviter_id,
            target_role=target_role,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def by_hash(
        self, h: str
    ) -> PlaylistInviteToken | None:
        r = await self._session.execute(
            select(PlaylistInviteToken)
            .where(PlaylistInviteToken.token_hash == h)
            .limit(1)
        )
        return r.scalars().first()

    async def delete_by_id(self, row_id: int) -> None:
        await self._session.execute(
            delete(PlaylistInviteToken).where(
                PlaylistInviteToken.id == row_id
            )
        )
        await self._session.flush()
