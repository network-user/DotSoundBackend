"""Admin-only API endpoints.

All routes require is_admin=True (enforced via require_admin dependency).
Admins can manage all tracks, users, and complaints regardless of ownership.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin
from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.schemas.complaint import ComplaintResponse
from app.schemas.track import TrackResponse
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Response / request schemas ───────────────────────────────────────────────


class AdminTrackResponse(TrackResponse):
    uploaded_by_id: int | None = None
    is_active: bool = True


class AdminComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    reported_by_user_id: int
    reason: str
    contact_email: str | None
    is_resolved: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=128)
    is_active: bool | None = None
    is_admin: bool | None = None


class AdminTrackListResponse(BaseModel):
    items: list[AdminTrackResponse]
    total: int
    page: int
    size: int


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int


class AdminComplaintListResponse(BaseModel):
    items: list[AdminComplaintResponse]
    total: int
    page: int
    size: int


# ── Tracks ────────────────────────────────────────────────────────────────────


@router.get(
    "/tracks",
    response_model=AdminTrackListResponse,
    summary="[Admin] List all tracks including hidden",
)
@limiter.limit("60/minute")
async def admin_list_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminTrackListResponse:
    offset = (page - 1) * size
    result = await session.execute(
        select(Track).order_by(Track.created_at.desc()).offset(offset).limit(size)
    )
    tracks = list(result.scalars().all())

    count_result = await session.execute(
        select(Track).order_by(None)
    )
    total = len(count_result.scalars().all())

    return AdminTrackListResponse(
        items=[AdminTrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        size=size,
    )


@router.delete(
    "/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Hard-delete any track",
)
@limiter.limit("30/minute")
async def admin_delete_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> None:
    result = await session.execute(
        select(Track).where(Track.id == track_id)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if track.source == "internal" and track.file_key:
        try:
            await s3.delete_object(track.file_key)
        except Exception:
            logger.warning(
                "admin_s3_delete_failed",
                track_id=track_id,
                file_key=track.file_key,
            )
    if track.cover_key:
        try:
            await s3.delete_object(track.cover_key)
        except Exception:
            logger.warning(
                "admin_s3_cover_delete_failed",
                track_id=track_id,
                cover_key=track.cover_key,
            )
    await session.delete(track)
    logger.info("admin_track_deleted", track_id=track_id)


@router.patch(
    "/tracks/{track_id}/visibility",
    response_model=AdminTrackResponse,
    summary="[Admin] Toggle track active/hidden status",
)
@limiter.limit("60/minute")
async def admin_toggle_track_active(
    request: Request,
    track_id: int,
    is_active: bool = Query(...),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminTrackResponse:
    result = await session.execute(
        select(Track).where(Track.id == track_id)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    track.is_active = is_active
    logger.info(
        "admin_track_visibility_changed",
        track_id=track_id,
        is_active=is_active,
    )
    return AdminTrackResponse.model_validate(track)


# ── Users ─────────────────────────────────────────────────────────────────────


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


# ── Complaints ────────────────────────────────────────────────────────────────


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

    count_q = select(Complaint)
    if unresolved_only:
        count_q = count_q.where(Complaint.is_resolved.is_(False))
    count_result = await session.execute(count_q)
    total = len(count_result.scalars().all())

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
