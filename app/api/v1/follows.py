"""Follow/unfollow endpoints and follower/following listings."""

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.follow import (
    FollowerResponse,
    FollowListResponse,
    FollowToggleResponse,
)
from app.services.follow_service import FollowService

router = APIRouter(prefix="/users", tags=["follows"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "/{user_id}/follow",
    response_model=FollowToggleResponse,
    summary="Toggle follow for a user",
)
@limiter.limit("60/minute")
async def toggle_follow(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FollowToggleResponse:
    structlog.contextvars.bind_contextvars(
        follower_id=current_user.id, following_id=user_id
    )
    service = FollowService(session)
    following = await service.toggle(
        follower_id=current_user.id, following_id=user_id
    )
    return FollowToggleResponse(user_id=user_id, following=following)


@router.get(
    "/{user_id}/follow/status",
    summary="Check if current user follows target",
)
@limiter.limit("120/minute")
async def follow_status(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = FollowService(session)
    is_following = await service.is_following(
        follower_id=current_user.id,
        following_id=user_id,
    )
    return {"following": is_following}


@router.get(
    "/{user_id}/followers",
    response_model=FollowListResponse,
    summary="List followers of a user",
)
@limiter.limit("120/minute")
async def list_followers(
    request: Request,
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = FollowService(session)
    users, total = await service.list_followers(user_id, page, size)
    items = [FollowerResponse.model_validate(u) for u in users]
    return FollowListResponse(items=items, total=total)


@router.get(
    "/{user_id}/following",
    response_model=FollowListResponse,
    summary="List users that a user is following",
)
@limiter.limit("120/minute")
async def list_following(
    request: Request,
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = FollowService(session)
    users, total = await service.list_following(user_id, page, size)
    items = [FollowerResponse.model_validate(u) for u in users]
    return FollowListResponse(items=items, total=total)
