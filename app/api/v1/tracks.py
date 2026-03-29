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
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db
from app.schemas.track import (
    PlayResponse,
    StreamResponse,
    TrackListResponse,
    TrackResponse,
    TrackUpdateRequest,
    TrackUploadResponse,
)
from app.services.track_service import TrackService
from app.services.upload_service import UploadService

router = APIRouter(prefix="/tracks", tags=["tracks"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "",
    response_model=TrackListResponse,
    summary="List active tracks with optional search",
)
@limiter.limit("200/minute")
async def list_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Search query"),
    session: AsyncSession = Depends(get_db),
) -> TrackListResponse:
    service = TrackService(session)
    if q:
        structlog.contextvars.bind_contextvars(search_query=q)
        tracks, total = await service.search(q, page=page, size=size)
    else:
        tracks, total = await service.list_tracks(page=page, size=size)
    return TrackListResponse(
        items=[TrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/cover_proxy",
    summary="Redirect to presigned cover URL by MinIO key",
)
@limiter.limit("600/minute")
async def cover_proxy(
    request: Request,
    key: str = Query(..., description="MinIO object key"),
) -> RedirectResponse:
    if ".." in key or key.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key",
        )
    url = await s3.get_presigned_url(key)
    return RedirectResponse(url=url, status_code=302)


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
    uploader_id: int | None = Form(None),
    is_public: bool = Form(True),
    cover: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_db),
) -> TrackUploadResponse:
    structlog.contextvars.bind_contextvars(
        title=title,
        artist=artist,
        uploader_id=uploader_id,
    )
    logger.info("track_upload_endpoint_called")
    service = UploadService(session)
    track = await service.upload_track(
        file=file,
        title=title,
        artist=artist,
        cover=cover,
        uploader_id=uploader_id,
        is_public=is_public,
    )
    return TrackUploadResponse.model_validate(track)


@router.get(
    "/my",
    response_model=TrackListResponse,
    summary="List tracks uploaded by a specific user",
)
@limiter.limit("120/minute")
async def list_my_tracks(
    request: Request,
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> TrackListResponse:
    service = TrackService(session)
    tracks, total = await service.list_by_user(user_id, page=page, size=size)
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
    requester_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
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
        user_id=requester_id,
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
    requester_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
) -> None:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.delete_by_owner(
        track_id=track_id, user_id=requester_id
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
                "s3_delete_failed", track_id=track_id, file_key=track.file_key
            )
    logger.info("track_deleted", track_id=track_id, requester_id=requester_id)


@router.get(
    "/{track_id}/stream",
    response_model=StreamResponse,
    summary="Get URL to stream the audio",
)
@limiter.limit("300/minute")
async def stream_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> StreamResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if track.source == "soundcloud":
        if not track.sc_uri:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SC track missing URI",
            )
        from app.services.soundcloud_service import SoundCloudService
        from app.config import settings
        sc_service = SoundCloudService(settings.sc_client_id, session)
        widget_url = sc_service.build_widget_url(track.sc_uri)
        return StreamResponse(
            track_id=track_id, url=widget_url, expires_in=0
        )
    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file",
        )
    url = await s3.get_presigned_url(track.file_key)
    logger.info("stream_url_generated", track_id=track_id)
    return StreamResponse(track_id=track_id, url=url)


@router.post(
    "/{track_id}/play",
    response_model=PlayResponse,
    summary="Increment play count for a track",
)
@limiter.limit("20/minute")
async def play_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> PlayResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    from app.repositories.track import TrackRepository

    repo = TrackRepository(session)
    found = await repo.increment_play_count(track_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    track = await repo.get_by_id(track_id)
    play_count = track.play_count if track else 0
    logger.info(
        "play_count_updated",
        track_id=track_id,
        play_count=play_count,
    )
    return PlayResponse(track_id=track_id, play_count=play_count)


@router.get(
    "/{track_id}/cover",
    response_model=StreamResponse,
    summary="Get presigned URL for the track cover image",
)
@limiter.limit("300/minute")
async def get_cover(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> StreamResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track or not track.cover_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover not found",
        )
    url = await s3.get_presigned_url(track.cover_key)
    return StreamResponse(track_id=track_id, url=url)


@router.get(
    "/{track_id}",
    response_model=TrackResponse,
    summary="Get a single track by ID",
)
@limiter.limit("300/minute")
async def get_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    return TrackResponse.model_validate(track)
