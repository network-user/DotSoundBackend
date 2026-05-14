from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_capability import AdminCapability


def _sorted_caps(caps: frozenset[str]) -> list[str]:
    return sorted(caps)


class AdminCapabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_capability(
        self, user_id: int, capability: str
    ) -> bool:
        result = await self._session.execute(
            select(AdminCapability.id).where(
                AdminCapability.user_id == user_id,
                AdminCapability.capability == capability,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_for_user(
        self, user_id: int
    ) -> list[str]:
        result = await self._session.execute(
            select(AdminCapability.capability).where(
                AdminCapability.user_id == user_id
            )
        )
        return [
            str(row) for row in result.scalars().all()
        ]

    async def list_grants_for_user(
        self, user_id: int
    ) -> list[AdminCapability]:
        result = await self._session.execute(
            select(AdminCapability).where(
                AdminCapability.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def find_grant(
        self, user_id: int, capability: str
    ) -> AdminCapability | None:
        result = await self._session.execute(
            select(AdminCapability).where(
                AdminCapability.user_id == user_id,
                AdminCapability.capability == capability,
            )
        )
        return result.scalar_one_or_none()

    async def grant_all_known_if_empty(
        self,
        *,
        user_id: int,
        capabilities: frozenset[str],
    ) -> bool:
        if await self.list_for_user(user_id):
            return False
        now = datetime.now(UTC)
        for cap in _sorted_caps(capabilities):
            self._session.add(
                AdminCapability(
                    user_id=user_id,
                    capability=cap,
                    granted_by=None,
                    granted_at=now,
                )
            )
        await self._session.flush()
        return True

    async def grant(
        self,
        *,
        user_id: int,
        capability: str,
        granted_by: int | None,
    ) -> AdminCapability:
        row = AdminCapability(
            user_id=user_id,
            capability=capability,
            granted_by=granted_by,
            granted_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def revoke(self, row: AdminCapability) -> None:
        await self._session.delete(row)
        await self._session.flush()
