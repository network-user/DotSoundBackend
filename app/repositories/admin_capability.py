from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_capability import AdminCapability


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
