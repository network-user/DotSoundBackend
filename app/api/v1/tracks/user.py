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
from app.services.track_response_build import (
    build_track_response,
    dedupe_and_build_track_list,
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
_CURRENT_UPLOAD_TERMS_VERSION = "2026-04-15"


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
    use_profile_artist: bool = Form(False),
    genre: str | None = Form(None, max_length=100),
    is_public: bool = Form(True),
    upload_terms_accepted: bool = Form(False),
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
    if not upload_terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload terms must be accepted",
        )
    service = UploadService(session)
    effective_artist = artist
    if use_profile_artist:
        effective_artist = current_user.display_name
        if not effective_artist:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name is required for profile artist mode",
            )
    track = await service.upload_track(
        file=file,
        title=title,
        artist=effective_artist,
        use_profile_artist=use_profile_artist,
        genre=genre,
        cover=cover,
        uploader_id=current_user.id,
        is_public=is_public,
        background_tasks=background_tasks,
    )

    from app.models.upload_meta import TrackUploadMeta
    meta = TrackUploadMeta(
        track_id=track.id,
        upload_ip=(
            request.client.host
            if request.client
            else None
        ),
        upload_user_agent=request.headers.get(
            "user-agent"
        ),
        upload_terms_accepted=True,
        upload_terms_version=(
            _CURRENT_UPLOAD_TERMS_VERSION
        ),
    )
    session.add(meta)
    await session.flush()

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
    playable: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    service = TrackService(session)
    tracks, total = await service.list_by_user(
        current_user.id,
        page=page,
        size=size,
        playable_only=playable,
    )
    items = await dedupe_and_build_track_list(session, tracks)
    return TrackListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/my/imported",
    response_model=TrackListResponse,
)
@limiter.limit("120/minute")
async def list_my_imported_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    source: str | None = Query(None, max_length=32),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    service = TrackService(session)
    tracks, total = await service.list_imported_by_user(
        current_user.id,
        page=page,
        size=size,
        source_filter=source or None,
    )
    items = await dedupe_and_build_track_list(session, tracks)
    return TrackListResponse(
        items=items,
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
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    service = TrackService(session)
    if current_user.is_admin:
        track = await service.admin_update_track(
            track_id=track_id,
            **fields,
        )
    else:
        track = await service.update_track(
            track_id=track_id,
            user_id=current_user.id,
            **fields,
        )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found or access denied",
        )
    return await build_track_response(session, track)


@router.delete(
    "/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an owned track (restorable in /me/trash)",
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
    logger.info(
        "track_soft_deleted",
        track_id=track_id,
        user_id=current_user.id,
    )


@router.post(
    "/{track_id}/restore",
    response_model=TrackResponse,
    summary="Restore a soft-deleted track within grace period",
)
@limiter.limit("30/minute")
async def restore_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.restore_by_owner(
        track_id=track_id, user_id=current_user.id
    )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not in trash or not owned",
        )
    logger.info(
        "track_restored",
        track_id=track_id,
        user_id=current_user.id,
    )
    return await build_track_response(session, track)


@router.get(
    "/me/trash",
    response_model=TrackListResponse,
    summary="List soft-deleted tracks for the current user",
)
@limiter.limit("60/minute")
async def list_my_trash(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    service = TrackService(session)
    tracks, total = await service.list_my_trash(
        user_id=current_user.id, page=page, size=size
    )
    items = await dedupe_and_build_track_list(session, tracks)
    return TrackListResponse(
        items=items, total=total, page=page, size=size
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
    if user.is_admin:
        return track
    if track.uploaded_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the track owner",
        )
    if track.catalog_type != "ugc":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit imported tracks",
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

    old_cover_key = track.cover_key

    cover_key = await s3.upload_cover(
        data=data,
        content_type=mime,
        user_id=current_user.id,
    )
    track.cover_key = cover_key
    await session.flush()
    await session.refresh(track)

    if old_cover_key:
        try:
            await s3.delete_object(old_cover_key)
        except Exception:
            pass

    logger.info(
        "track_cover_uploaded",
        track_id=track_id,
        cover_key=cover_key,
    )
    return await build_track_response(session, track)


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
    return await build_track_response(session, track)


_ALLOWED_VIDEO_MIMES = frozenset(
    {"video/mp4", "video/webm"}
)

from dotsound_private_core.services.upload_policy import (
    MAX_VIDEO_BYTES as _MAX_VIDEO_BYTES,
)


@router.post(
    "/{track_id}/video",
    response_model=TrackResponse,
)
@limiter.limit("5/minute")
async def upload_track_video(
    request: Request,
    track_id: int,
    video: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    track = await _get_owned_track(
        track_id, current_user, session
    )

    mime = video.content_type or ""
    if mime not in _ALLOWED_VIDEO_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Video must be MP4 or WebM",
        )

    data = await video.read()
    if len(data) > _MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Video exceeds {_MAX_VIDEO_BYTES // (1024 * 1024)} MB limit",
        )

    from app.services.file_validator import validate_video_async
    await validate_video_async(data, video.filename)

    if track.video_key:
        try:
            await s3.delete_object(track.video_key)
        except Exception:
            pass

    import re
    safe_name = re.sub(
        r"[^\w.\-]", "_", video.filename or "video"
    )[:100]
    raw_key = f"temp/video/{track.id}_{safe_name}"
    await s3.upload_object(
        key=raw_key, data=data, content_type=mime
    )

    track.video_processing_status = "processing"
    await session.flush()

    from app.services.video_transcoding import (
        transcode_video,
    )
    await transcode_video.kiq(
        track_id=track.id,
        raw_key=raw_key,
        original_filename=video.filename or "video.mp4",
    )

    await session.refresh(track)
    return await build_track_response(session, track)


@router.delete(
    "/{track_id}/video",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("10/minute")
async def delete_track_video(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    track = await _get_owned_track(
        track_id, current_user, session
    )
    if track.video_key:
        try:
            await s3.delete_object(track.video_key)
        except Exception:
            pass
        track.video_key = None
        await session.flush()


@router.post(
    "/{track_id}/cover/restore",
    response_model=TrackResponse,
)
@limiter.limit("5/minute")
async def restore_external_cover(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackResponse:
    track = await _get_owned_track(
        track_id, current_user, session
    )

    if track.source != "soundcloud" or not track.sc_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SoundCloud tracks can restore covers",
        )

    from app.config import settings
    from app.services.soundcloud_service import SoundCloudService

    sc_service = SoundCloudService(
        settings.sc_client_id, session
    )
    sc_data = await sc_service.resolve_url(track.sc_url)
    artwork_url: str | None = sc_data.get("artwork_url")
    if not artwork_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No artwork found on SoundCloud for this track",
        )

    cover_key = await sc_service._download_thumbnail(
        artwork_url, current_user.id
    )

    old_cover_key = track.cover_key
    track.cover_key = cover_key
    await session.flush()
    await session.refresh(track)

    if old_cover_key and old_cover_key != cover_key:
        try:
            await s3.delete_object(old_cover_key)
        except Exception:
            pass

    logger.info(
        "track_cover_restored",
        track_id=track_id,
        cover_key=cover_key,
    )
    return await build_track_response(session, track)
