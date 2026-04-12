from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.block import BlockRepository

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class BlockService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._repo = BlockRepository(session)

    async def block_user(
        self, blocker_id: int, blocked_id: int
    ) -> None:
        if blocker_id == blocked_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot block yourself",
            )
        existing = await self._repo.get_block(
            blocker_id, blocked_id
        )
        if existing:
            return
        await self._repo.block(
            blocker_id, blocked_id
        )
        logger.info(
            "user_blocked",
            blocker=blocker_id,
            blocked=blocked_id,
        )

    async def unblock_user(
        self, blocker_id: int, blocked_id: int
    ) -> None:
        await self._repo.unblock(
            blocker_id, blocked_id
        )
        logger.info(
            "user_unblocked",
            blocker=blocker_id,
            blocked=blocked_id,
        )

    async def is_blocked(
        self, user_a: int, user_b: int
    ) -> bool:
        return await self._repo.is_blocked(
            user_a, user_b
        )

    async def get_blocked_users(
        self, user_id: int
    ) -> list[int]:
        return await self._repo.get_blocked_users(
            user_id
        )
