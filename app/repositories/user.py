import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> User | None:
        logger.debug(
            "db_get_by_telegram_id",
            telegram_id=telegram_id,
        )
        result = await self._session.execute(
            select(User).where(
                User.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(
        self, email: str
    ) -> User | None:
        logger.debug("db_get_by_email", email=email)
        result = await self._session.execute(
            select(User).where(
                User.email == email.lower()
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(
            telegram_id
        )
        if user:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            if not user.avatar_seed:
                user.avatar_seed = uuid.uuid4().hex
            await self._session.flush()
            logger.debug(
                "db_user_updated",
                telegram_id=telegram_id,
            )
            return user, False
        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            avatar_seed=uuid.uuid4().hex,
            auth_provider="telegram",
        )
        logger.debug(
            "db_user_created",
            telegram_id=telegram_id,
        )
        return user, True

    async def upsert_by_email(
        self, email: str
    ) -> tuple[User, bool]:
        normalized = email.lower().strip()
        user = await self.get_by_email(normalized)
        if user:
            return user, False
        local_part = normalized.split("@")[0][:64]
        user = await self.create(
            email=normalized,
            email_verified=True,
            first_name=local_part,
            avatar_seed=uuid.uuid4().hex,
            auth_provider="email",
        )
        logger.debug(
            "db_user_created_by_email",
            email=normalized,
        )
        return user, True

    async def update_display_name(
        self, user_id: int, display_name: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.display_name = display_name
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def get_first_user(self) -> User | None:
        result = await self._session.execute(
            select(User).order_by(User.id).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_avatar_key(
        self, user_id: int, avatar_key: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.avatar_key = avatar_key
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def soft_delete(
        self, user_id: int
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        await self._session.flush()
        return user

    async def restore(
        self, user_id: int
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user or user.deleted_at is None:
            return None
        user.deleted_at = None
        user.is_active = True
        await self._session.flush()
        return user

    async def get_by_ids(
        self, ids: list[int]
    ) -> dict[int, User]:
        if not ids:
            return {}
        uniq = list(dict.fromkeys(ids))
        result = await self._session.execute(
            select(User).where(User.id.in_(uniq))
        )
        rows = result.scalars().all()
        return {u.id: u for u in rows}

    async def search(
        self, query: str, limit: int = 20
    ) -> list[User]:
        pattern = f"%{query}%"
        result = await self._session.execute(
            select(User)
            .where(
                User.is_active.is_(True),
                (
                    User.username.ilike(pattern)
                    | User.first_name.ilike(pattern)
                    | User.last_name.ilike(pattern)
                    | User.display_name.ilike(
                        pattern
                    )
                ),
            )
            .limit(limit)
        )
        return list(result.scalars().all())
