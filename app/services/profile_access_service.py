from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserResponse
from app.services.follow_service import FollowService
from app.services.user_service import UserService

_ALLOWED_VISIBILITY = frozenset(
    {"public", "followers_only", "hidden"}
)


def coerced_visibility(user: User) -> str:
    raw = getattr(user, "profile_visibility", None) or "public"
    if raw not in _ALLOWED_VISIBILITY:
        return "public"
    return raw


class ProfileAccessService:
    def __init__(self, session: AsyncSession) -> None:
        self._follow = FollowService(session)
        self._users = UserService(session)

    async def get_owner_or_404(self, user_id: int) -> User:
        user = await self._users.get_by_id(user_id)
        if not user or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def can_view_extended(
        self,
        viewer: User | None,
        owner: User,
    ) -> bool:
        if owner.deleted_at is not None:
            return False
        if viewer is not None and viewer.id == owner.id:
            return True
        vis = coerced_visibility(owner)
        if vis == "public":
            return True
        if vis == "hidden":
            return False
        if viewer is None:
            return False
        return await self._follow.is_following(
            viewer.id,
            owner.id,
        )

    def raise_profile_restricted(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "profile_restricted",
                "message": "Profile content is not visible",
            },
        )

    async def require_extended(
        self,
        viewer: User | None,
        owner_id: int,
    ) -> User:
        owner = await self.get_owner_or_404(owner_id)
        if not await self.can_view_extended(viewer, owner):
            self.raise_profile_restricted()
        return owner


def build_user_profile_response(
    user: User,
    *,
    viewer: User | None,
    access_full: bool,
) -> UserResponse:
    vis = coerced_visibility(user)
    data = UserResponse.model_validate(user).model_dump()
    data["profile_visibility"] = vis
    data["profile_access"] = "full" if access_full else "limited"
    is_self = viewer is not None and viewer.id == user.id
    if not is_self:
        data["email"] = None
        data["email_verified"] = False
        data["telegram_id"] = None
        data["totp_enabled"] = False
        data["is_admin"] = False
        data["locale"] = None
    return UserResponse(**data)
