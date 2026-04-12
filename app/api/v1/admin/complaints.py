"""Admin endpoints for complaint management."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin
from app.models.complaint import Complaint
from app.models.user import User

from .schemas import AdminComplaintListResponse, AdminComplaintResponse

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
    offset = (page - 1) * size
    q = select(Complaint).order_by(Complaint.created_at.desc())
    if unresolved_only:
        q = q.where(Complaint.is_resolved.is_(False))
    result = await session.execute(q.offset(offset).limit(size))
    complaints = list(result.scalars().all())

    count_q = select(func.count(Complaint.id))
    if unresolved_only:
        count_q = count_q.where(
            Complaint.is_resolved.is_(False)
        )
    count_result = await session.execute(count_q)
    total = count_result.scalar_one()

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
    result = await session.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )
    complaint.is_resolved = True
    logger.info("admin_complaint_resolved", complaint_id=complaint_id)
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
    result = await session.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )
    await session.delete(complaint)
    logger.info("admin_complaint_deleted", complaint_id=complaint_id)
