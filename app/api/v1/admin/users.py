"""Admin endpoints for user management."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin
from app.models.user import User
from app.schemas.user import UserResponse

from .schemas import AdminUserListResponse, AdminUserUpdate

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="[Admin] List all users",
)
@limiter.limit("60/minute")
async def admin_list_users(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserListResponse:
    offset = (page - 1) * size
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(size)
    )
    users = list(result.scalars().all())

    count_result = await session.execute(select(User).order_by(None))
    total = len(count_result.scalars().all())

    return AdminUserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="[Admin] Update user (is_admin, is_active, display_name)",
)
@limiter.limit("30/minute")
async def admin_update_user(
    request: Request,
    user_id: int,
    data: AdminUserUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponse:
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    logger.info(
        "admin_user_updated",
        target_user_id=user_id,
        by_admin_id=admin.id,
        changes=data.model_dump(exclude_none=True),
    )
    return UserResponse.model_validate(user)
