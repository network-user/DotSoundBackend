import structlog
from dotsound_private_core.services.artist_normalizer import (
    normalize_name,
)
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.artist import ArtistRepository
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)
        self._artist_repo = ArtistRepository(session)

    async def register_or_update(
        self, data: UserCreate
    ) -> tuple[User, bool]:
        if data.telegram_id is None:
            raise ValueError(
                "telegram_id required for Telegram upsert"
            )
        user, created = await self._repo.upsert(
            telegram_id=data.telegram_id,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        logger.info(
            "user_upserted",
            telegram_id=data.telegram_id,
            created=created,
            user_id=user.id,
        )
        return user, created

    async def get_or_create_by_email(
        self, email: str
    ) -> tuple[User, bool]:
        user, created = await self._repo.upsert_by_email(
            email
        )
        logger.info(
            "user_email_upserted",
            email=email,
            created=created,
            user_id=user.id,
        )
        return user, created

    async def get_by_id(
        self, user_id: int
    ) -> User | None:
        user = await self._repo.get_by_id(user_id)
        if not user:
            user = await self._repo.get_by_telegram_id(
                user_id
            )

        if not user:
            logger.warning(
                "user_not_found", user_id=user_id
            )
        return user

    async def get_by_telegram_id(
        self, telegram_id: int
    ) -> User | None:
        return await self._repo.get_by_telegram_id(
            telegram_id
        )

    async def get_by_email(
        self, email: str
    ) -> User | None:
        return await self._repo.get_by_email(email)

    async def update_display_name(
        self, user_id: int, display_name: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        raw = display_name.strip()
        normalized = normalize_name(raw)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name is invalid",
            )
        conflict_user = await self._repo.find_by_display_name_normalized(
            normalized
        )
        if conflict_user and conflict_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Display name is already taken",
            )
        conflict_artist = await self._artist_repo.find_by_normalized_name(
            normalized
        )
        if conflict_artist and conflict_artist.owner_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Display name conflicts with existing artist",
            )
        user.display_name = raw
        user.display_name_normalized = normalized
        await self._repo._session.flush()
        await self._repo._session.refresh(user)

        owned_artist = await self._artist_repo.find_by_owner_user_id(user.id)
        if owned_artist and owned_artist.name_normalized != normalized:
            same_artist = await self._artist_repo.find_by_normalized_name(
                normalized
            )
            if same_artist and same_artist.id != owned_artist.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Display name conflicts with existing artist",
                )
            owned_artist.name = raw
            owned_artist.name_normalized = normalized
            await self._repo._session.flush()
        return user

    async def update_avatar_key(
        self, user_id: int, avatar_key: str
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        return await self._repo.update_avatar_key(
            user.id, avatar_key
        )

    async def request_deletion(
        self, user_id: int, confirmation: str
    ) -> bool:
        from dotsound_private_core.services.account_deletion_policy import (
            is_valid_confirmation,
        )
        if not is_valid_confirmation(confirmation):
            return False
        result = await self._repo.soft_delete(user_id)
        if result:
            logger.info(
                "user_deletion_requested",
                user_id=user_id,
            )
        return result is not None

    async def cancel_deletion(
        self, user_id: int
    ) -> bool:
        from dotsound_private_core.services.account_deletion_policy import (
            is_within_grace_period,
        )
        user = await self._repo.get_by_id(user_id)
        if (
            not user
            or user.deleted_at is None
            or not is_within_grace_period(user.deleted_at)
        ):
            return False
        result = await self._repo.restore(user_id)
        if result:
            logger.info(
                "user_deletion_cancelled",
                user_id=user_id,
            )
        return result is not None
