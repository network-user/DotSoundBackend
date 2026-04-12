from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppSettings
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_settings
from app.models.user import User
from app.repositories.complaint import ComplaintRepository
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintSubmitResponse,
)
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints")


@router.post("", response_model=ComplaintSubmitResponse)
@limiter.limit("10/minute")
async def submit_complaint(
    request: Request,
    body: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    cfg: AppSettings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ComplaintSubmitResponse:
    svc = ComplaintService(db)
    try:
        complaint, track_hidden = await svc.submit(
            track_id=body.track_id,
            user_id=current_user.id,
            reason=body.reason,
            contact_email=body.contact_email,
            threshold=cfg.complaint_threshold,
        )
    except ValueError as exc:
        if str(exc) == "already_reported":
            raise HTTPException(
                status_code=409,
                detail="Вы уже подавали жалобу на этот трек",
            )
        raise
    return ComplaintSubmitResponse(
        complaint=ComplaintResponse.model_validate(complaint),
        track_hidden=track_hidden,
    )


@router.get(
    "/{track_id}", response_model=list[ComplaintResponse]
)
@limiter.limit("60/minute")
async def list_complaints(
    request: Request,
    track_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ComplaintResponse]:
    repo = ComplaintRepository(db)
    complaints = await repo.list_by_track(track_id)
    return [
        ComplaintResponse.model_validate(c)
        for c in complaints
    ]
