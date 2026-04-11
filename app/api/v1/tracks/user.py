import mimetypes

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from app.models.track import Track
from app.models.user import User
from app.schemas.track import (
    TrackListResponse,
    TrackResponse,
    TrackUpdateRequest,
    TrackUploadResponse,
)
from app.services.cover_worker import (
    generate_and_upload_cover,
)
from app.services.track_service import TrackService
from app.services.upload_service import UploadService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_ALLOWED_COVER_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_MAX_COVER_BYTES = 5 * 1024 * 1024


@router.post(
    "/upload",
    response_model=TrackUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def upload_track(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., max_length=256),
    artist: str | None = Form(None, max_length=256),
    genre: str | None = Form(None, max_length=100),
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
        genre=genre,
        cover=cover,
        uploader_id=current_user.id,
        is_public=is_public,
        background_tasks=background_tasks,
    )
    return TrackUploadResponse.model_validate(track)


@router.get(
    "/my",
    response_model=TrackListResponse,
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
        items=[
            TrackResponse.model_validate(t)
            for t in tracks
        ],
        total=total,
        page=page,
        size=size,
    )


@router.patch(
    "/{track_id}",
    response_model=TrackResponse,
)
@limiter.limit("60/minute")
async def update_track(
    request: Request,
    track_id: int,
    data: TrackUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(
        track_id=track_id
    )
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
)
@limiter.limit("30/minute")
async def delete_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(
        track_id=track_id
    )
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
    logger.info(
        "track_deleted",
        track_id=track_id,
        user_id=current_user.id,
    )


async def _get_owned_track(
    track_id: int,
    user: User,
    session: AsyncSession,
) -> Track:
    track = await session.get(Track, track_id)
    if not track or not track.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if track.uploaded_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the track owner",
        )
    return track


@router.post(
    "/{track_id}/cover",
    response_model=TrackResponse,
)
@limiter.limit("10/minute")
async def upload_track_cover(
    request: Request,
    track_id: int,
    cover: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    track = await _get_owned_track(
        track_id, current_user, session
    )

    mime = cover.content_type or ""
    if not mime or mime == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(
            cover.filename or ""
        )
        mime = guessed or mime
    if mime not in _ALLOWED_COVER_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Cover must be JPEG, PNG or WebP",
        )

    data = await cover.read()
    if len(data) > _MAX_COVER_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Cover exceeds 5 MB limit",
        )

    if track.cover_key:
        try:
            await s3.delete_object(track.cover_key)
        except Exception:
            pass

    cover_key = await s3.upload_cover(
        data=data,
        content_type=mime,
        user_id=current_user.id,
    )
    track.cover_key = cover_key
    await session.flush()
    await session.refresh(track)

    logger.info(
        "track_cover_uploaded",
        track_id=track_id,
        cover_key=cover_key,
    )
    return TrackResponse.model_validate(track)


@router.post(
    "/{track_id}/cover/generate",
    response_model=TrackResponse,
)
@limiter.limit("3/minute")
async def regenerate_track_cover(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    track = await _get_owned_track(
        track_id, current_user, session
    )

    await generate_and_upload_cover.kiq(track.id)

    logger.info(
        "track_cover_regenerate_queued",
        track_id=track_id,
    )
    return TrackResponse.model_validate(track)
