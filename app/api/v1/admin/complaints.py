"""Admin endpoints for complaint management."""

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
from app.services.admin_service import AdminService

from .schemas import (
    AdminComplaintListResponse,
    AdminComplaintResponse,
)

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "/complaints",
    response_model=AdminComplaintListResponse,
    summary="[Admin] List all complaints",
)
@limiter.limit("60/minute")
async def admin_list_complaints(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unresolved_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminComplaintListResponse:
    service = AdminService(session)
    complaints, total = await service.list_complaints(
        page=page,
        size=size,
        unresolved_only=unresolved_only,
    )
    return AdminComplaintListResponse(
        items=[AdminComplaintResponse.model_validate(c) for c in complaints],
        total=total,
        page=page,
        size=size,
    )


@router.patch(
    "/complaints/{complaint_id}/resolve",
    response_model=AdminComplaintResponse,
    summary="[Admin] Mark a complaint as resolved",
)
@limiter.limit("60/minute")
async def admin_resolve_complaint(
    request: Request,
    complaint_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminComplaintResponse:
    service = AdminService(session)
    complaint = await service.resolve_complaint(complaint_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )
    logger.info(
        "admin_complaint_resolved",
        complaint_id=complaint_id,
    )
    return AdminComplaintResponse.model_validate(complaint)


@router.delete(
    "/complaints/{complaint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Delete a complaint",
)
@limiter.limit("30/minute")
async def admin_delete_complaint(
    request: Request,
    complaint_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> None:
    service = AdminService(session)
    deleted = await service.delete_complaint(complaint_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )
    logger.info(
        "admin_complaint_deleted",
        complaint_id=complaint_id,
    )
