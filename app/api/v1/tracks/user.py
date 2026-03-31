"""Track endpoints for authenticated users — upload, list own, update, delete."""

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.track import (
    TrackListResponse,
    TrackResponse,
    TrackUpdateRequest,
    TrackUploadResponse,
)
from app.services.track_service import TrackService
from app.services.upload_service import UploadService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "/upload",
    response_model=TrackUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new audio track (multipart/form-data)",
)
@limiter.limit("10/minute")
async def upload_track(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(..., max_length=256),
    artist: str | None = Form(None, max_length=256),
    is_public: bool = Form(True),
    cover: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackUploadResponse:
    structlog.contextvars.bind_contextvars(
        title=title,
        artist=artist,
        uploader_id=current_user.id,
    )
    logger.info("track_upload_endpoint_called")
    service = UploadService(session)
    track = await service.upload_track(
        file=file,
        title=title,
        artist=artist,
        cover=cover,
        uploader_id=current_user.id,
        is_public=is_public,
    )
    return TrackUploadResponse.model_validate(track)


@router.get(
    "/my",
    response_model=TrackListResponse,
    summary="List tracks uploaded by the authenticated user",
)
@limiter.limit("120/minute")
async def list_my_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    service = TrackService(session)
    tracks, total = await service.list_by_user(
        current_user.id, page=page, size=size
    )
    return TrackListResponse(
        items=[TrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        size=size,
    )


@router.patch(
    "/{track_id}",
    response_model=TrackResponse,
    summary="Update track visibility (owner only)",
)
@limiter.limit("60/minute")
async def update_track(
    request: Request,
    track_id: int,
    data: TrackUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    if data.is_public is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    service = TrackService(session)
    track = await service.update_visibility(
        track_id=track_id,
        user_id=current_user.id,
        is_public=data.is_public,
    )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found or access denied",
        )
    return TrackResponse.model_validate(track)


@router.delete(
    "/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete own track",
)
@limiter.limit("30/minute")
async def delete_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.delete_by_owner(
        track_id=track_id, user_id=current_user.id
    )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found or access denied",
        )
    if track.source == "internal" and track.file_key:
        try:
            await s3.delete_object(track.file_key)
        except Exception:
            logger.warning(
                "s3_delete_failed",
                track_id=track_id,
                file_key=track.file_key,
            )
    logger.info("track_deleted", track_id=track_id, user_id=current_user.id)
