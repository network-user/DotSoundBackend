from __future__ import annotations

import structlog
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import UserBlock

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class BlockRepository:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._s = session

    async def block(
        self, blocker_id: int, blocked_id: int
    ) -> UserBlock:
        b = UserBlock(
            blocker_id=blocker_id,
            blocked_id=blocked_id,
        )
        self._s.add(b)
        await self._s.flush()
        return b

    async def unblock(
        self, blocker_id: int, blocked_id: int
    ) -> None:
        await self._s.execute(
            delete(UserBlock).where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
        )
        await self._s.flush()

    async def is_blocked(
        self, user_a: int, user_b: int
    ) -> bool:
        row = await self._s.execute(
            select(UserBlock).where(
                or_(
                    (
                        (
                            UserBlock.blocker_id
                            == user_a
                        )
                        & (
                            UserBlock.blocked_id
                            == user_b
                        )
                    ),
                    (
                        (
                            UserBlock.blocker_id
                            == user_b
                        )
                        & (
                            UserBlock.blocked_id
                            == user_a
                        )
                    ),
                )
            )
        )
        return row.scalar_one_or_none() is not None

    async def get_blocked_users(
        self, user_id: int
    ) -> list[int]:
        rows = await self._s.execute(
            select(UserBlock.blocked_id).where(
                UserBlock.blocker_id == user_id
            )
        )
        return list(rows.scalars().all())

    async def get_block(
        self, blocker_id: int, blocked_id: int
    ) -> UserBlock | None:
        return await self._s.get(
            UserBlock, (blocker_id, blocked_id)
        )
