"""Admin endpoints for user management."""

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.admin_service import AdminService

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
    is_active: bool | None = Query(None),
    is_admin: bool | None = Query(None),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserListResponse:
    service = AdminService(session)
    users, total = await service.list_users(
        page=page,
        size=size,
        is_active=is_active,
        is_admin=is_admin,
        search=search,
    )
    return AdminUserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary=("[Admin] Update user " "(is_admin, is_active, display_name)"),
)
@limiter.limit("30/minute")
async def admin_update_user(
    request: Request,
    user_id: int,
    data: AdminUserUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponse:
    service = AdminService(session)
    user = await service.update_user(
        user_id,
        display_name=data.display_name,
        is_active=data.is_active,
        is_admin=data.is_admin,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    logger.info(
        "admin_user_updated",
        target_user_id=user_id,
        by_admin_id=admin.id,
        changes=data.model_dump(exclude_none=True),
    )
    return UserResponse.model_validate(user)
