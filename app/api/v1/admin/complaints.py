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
from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.user import User
from app.services.admin_service import AdminService
from app.services.notification_service import (
    NotificationService,
)

from .schemas import (
    AdminComplaintListResponse,
    AdminComplaintResponse,
    AdminComplaintUpdateRequest,
)

_ACTION_TITLES: dict[str, str] = {
    "accept": "Жалоба принята",
    "dismiss": "Жалоба отклонена",
    "in_progress": "Жалоба в работе",
}

_ACTION_BODIES: dict[str, str] = {
    "accept": (
        "Жалоба на трек принята модератором. "
        "Доступ к треку ограничен."
    ),
    "dismiss": (
        "Жалоба на трек рассмотрена и отклонена."
    ),
    "in_progress": (
        "Жалоба на трек получена и взята в работу."
    ),
}

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
    _admin: User = Depends(require_admin_session),
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
    _admin: User = Depends(require_admin_session),
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


@router.patch(
    "/complaints/{complaint_id}",
    response_model=AdminComplaintResponse,
    summary="[Admin] Resolve / dismiss / mark in-progress",
)
@limiter.limit("60/minute")
async def admin_update_complaint(
    request: Request,
    complaint_id: int,
    body: AdminComplaintUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminComplaintResponse:
    service = AdminService(session)
    try:
        result = await service.apply_complaint_action(
            complaint_id,
            action=body.action,
            note=body.note,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )
    complaint, track_hidden = result
    logger.info(
        "admin_complaint_action",
        complaint_id=complaint_id,
        action=body.action,
        track_hidden=track_hidden,
    )

    notif = NotificationService(session)
    try:
        await notif.create(
            user_id=complaint.reported_by_user_id,
            ntype=(
                "complaint_resolved"
                if body.action == "accept"
                else (
                    "complaint_dismissed"
                    if body.action == "dismiss"
                    else "complaint_in_progress"
                )
            ),
            title=_ACTION_TITLES.get(
                body.action, "Жалоба обновлена"
            ),
            body=_ACTION_BODIES.get(
                body.action, ""
            ),
            data={
                "complaint_id": complaint.id,
                "track_id": complaint.track_id,
                "action": body.action,
                "track_hidden": track_hidden,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "complaint_notification_failed",
            complaint_id=complaint_id,
            err=str(exc),
        )

    return AdminComplaintResponse.model_validate(
        complaint
    )


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
    _admin: User = Depends(require_admin_session),
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
