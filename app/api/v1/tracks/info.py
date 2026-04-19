"""Track information endpoint.

Provides AI-generated information about a track on demand.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.user import User
from app.repositories.track_info import TrackInfoRepository
from app.schemas.track_info import TrackInfoResponse
from app.services.track_info_service import TrackInfoService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_EMPTY_RESPONSE = TrackInfoResponse(
    status="pending", content=None, fetched_at=None
)


@router.get(
    "/{track_id}/info",
    response_model=TrackInfoResponse,
    summary="Get AI-generated info about a track (triggers fetch if stale/missing).",
)
async def get_track_info(
    track_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> TrackInfoResponse:
    from sqlalchemy import select
    from app.models.track import Track

    result = await db.execute(
        select(Track.id, Track.is_public, Track.uploaded_by_id).where(
            Track.id == track_id
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    _, is_public, owner_id = row
    if not is_public and (user is None or user.id != owner_id):
        raise HTTPException(status_code=403, detail="Access denied")

    svc = TrackInfoService(db)
    info = await svc.get_or_trigger(track_id)
    return TrackInfoResponse.model_validate(info)


@router.post(
    "/{track_id}/info/refresh",
    response_model=TrackInfoResponse,
    summary="Force-refresh AI-generated info for a track.",
)
@limiter.limit("5/minute")
async def refresh_track_info(
    request: Request,
    track_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrackInfoResponse:
    from sqlalchemy import select
    from app.models.track import Track

    result = await db.execute(
        select(Track.id, Track.is_public, Track.uploaded_by_id).where(
            Track.id == track_id
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    svc = TrackInfoService(db)
    info = await svc.get_or_trigger(track_id, force=True)
    return TrackInfoResponse.model_validate(info)
