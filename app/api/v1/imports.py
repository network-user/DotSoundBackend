from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.import_service import ImportService

router = APIRouter(prefix="/import", tags=["import"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class ImportStartRequest(BaseModel):
    track_indices: list[int]


class ImportJobResponse(BaseModel):
    id: int
    source: str
    status: str
    total_tracks: int
    completed_tracks: int
    failed_tracks: int
    tracks_data: dict[str, Any] | None = None

    class Config:
        from_attributes = True


@router.post(
    "/telegram",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def scan_telegram_profile(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.scan_telegram_profile(
        current_user.id
    )
    return ImportJobResponse.model_validate(job)


@router.post(
    "/{job_id}/start",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def start_import(
    request: Request,
    job_id: int,
    body: ImportStartRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.start_import(
        job_id, current_user.id, body.track_indices
    )
    return ImportJobResponse.model_validate(job)


@router.get(
    "/{job_id}/status",
    response_model=ImportJobResponse,
)
@limiter.limit("60/minute")
async def get_import_status(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.get_job_status(
        job_id, current_user.id
    )
    return ImportJobResponse.model_validate(job)


@router.get(
    "/active",
    response_model=ImportJobResponse | None,
)
@limiter.limit("30/minute")
async def get_active_import(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse | None:
    service = ImportService(session)
    job = await service.get_active_job(
        current_user.id
    )
    if not job:
        return None
    return ImportJobResponse.model_validate(job)


@router.post(
    "/{job_id}/cancel",
    response_model=ImportJobResponse,
)
@limiter.limit("10/minute")
async def cancel_import(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.cancel_job(
        job_id, current_user.id
    )
    return ImportJobResponse.model_validate(job)
