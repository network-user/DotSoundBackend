"""Admin endpoints for track management."""

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.user import User
from app.schemas.track import TrackUpdateRequest
from app.services.admin_service import AdminService
from app.services.transcoding import transcode_hls_only

from app.services.admin_track_context_service import (
    AdminTrackContextService,
    TrackNotFoundError,
)

from .schemas import (
    AdminTrackListResponse,
    AdminTrackResponse,
    AdminTrackGenrePatchRequest,
    BatchImportRequest,
    BatchImportResponse,
    BatchPromptRequest,
    BatchPromptResponse,
    SinglePromptResponse,
    TrackContextResponse,
    TrackContextUpdateRequest,
)

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    service = AdminService(session)
    tracks, total = await service.list_tracks(
        page=page,
        size=size,
        is_active=is_active,
        search=search,
    )
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
    _admin: User = Depends(require_admin_session),
) -> None:
    service = AdminService(session)
    deleted = await service.delete_track(track_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
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
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.set_track_visibility(track_id, is_active)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_visibility_changed",
        track_id=track_id,
        is_active=is_active,
    )
    return AdminTrackResponse.model_validate(track)


@router.patch(
    "/tracks/{track_id}",
    response_model=AdminTrackResponse,
    summary="[Admin] Update track metadata",
)
@limiter.limit("60/minute")
async def admin_update_track(
    request: Request,
    track_id: int,
    data: TrackUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    service = AdminService(session)
    track = await service.update_track(track_id, **fields)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_metadata_updated",
        track_id=track_id,
        fields=list(fields.keys()),
    )
    return AdminTrackResponse.model_validate(track)


@router.patch(
    "/tracks/{track_id}/genre",
    response_model=AdminTrackResponse,
    summary="[Admin] Quickly update track genre",
)
@limiter.limit("60/minute")
async def admin_update_track_genre(
    request: Request,
    track_id: int,
    data: AdminTrackGenrePatchRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.update_track(track_id, genre=data.genre)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_genre_updated",
        track_id=track_id,
        genre=data.genre,
    )
    return AdminTrackResponse.model_validate(track)


@router.post(
    "/tracks/transcode/{track_id}",
    summary="[Admin] Transcode a single track to HLS",
)
@limiter.limit("10/minute")
async def admin_transcode_track(
    request: Request,
    track_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> dict:
    service = AdminService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file to transcode",
        )
    background_tasks.add_task(transcode_hls_only, track_id, track.file_key)
    logger.info("admin_transcode_queued", track_id=track_id)
    return {"queued": True, "track_id": track_id}


@router.post(
    "/tracks/transcode/batch",
    summary=(
        "[Admin] Transcode all tracks without HLS to " "adaptive bitrate"
    ),
)
@limiter.limit("2/minute")
async def admin_transcode_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> dict:
    from app.models.track import Track

    result = await session.execute(
        select(Track).where(
            Track.source == "internal",
            Track.file_key.is_not(None),
            Track.hls_manifest_key.is_(None),
            Track.is_active.is_(True),
        )
    )
    tracks = list(result.scalars().all())
    for track in tracks:
        background_tasks.add_task(
            transcode_hls_only,
            track.id,
            track.file_key,
        )
    logger.info(
        "admin_transcode_batch_queued",
        count=len(tracks),
    )
    return {"queued": len(tracks)}


@router.post(
    "/tracks/context/batch-prompt",
    response_model=BatchPromptResponse,
    summary="[Admin] Generate batch prompt for selected tracks",
)
@limiter.limit("30/minute")
async def admin_batch_prompt(
    request: Request,
    data: BatchPromptRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> BatchPromptResponse:
    svc = AdminTrackContextService(session)
    prompt, count = await svc.batch_prompt(data.track_ids)
    logger.info("admin_batch_prompt_generated", track_count=count)
    return BatchPromptResponse(prompt=prompt, track_count=count)


@router.post(
    "/tracks/context/batch-import",
    response_model=BatchImportResponse,
    summary="[Admin] Import AI JSON response into track contexts",
)
@limiter.limit("10/minute")
async def admin_batch_import(
    request: Request,
    data: BatchImportRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> BatchImportResponse:
    svc = AdminTrackContextService(session)
    imported, errors = await svc.batch_import(data.raw_response)
    logger.info(
        "admin_batch_import_done",
        imported=imported,
        error_count=len(errors),
    )
    return BatchImportResponse(imported=imported, errors=errors)


@router.get(
    "/tracks/{track_id}/context",
    response_model=TrackContextResponse,
    summary="[Admin] Get current track context",
)
@limiter.limit("120/minute")
async def admin_get_track_context(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> TrackContextResponse:
    svc = AdminTrackContextService(session)
    row = await svc.get_context(track_id)
    if row is None:
        return TrackContextResponse(
            track_id=track_id,
            content=None,
            status="pending",
            fetched_at=None,
        )
    return TrackContextResponse.model_validate(row)


@router.patch(
    "/tracks/{track_id}/context",
    response_model=TrackContextResponse,
    summary="[Admin] Manually set track context",
)
@limiter.limit("60/minute")
async def admin_set_track_context(
    request: Request,
    track_id: int,
    data: TrackContextUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> TrackContextResponse:
    svc = AdminTrackContextService(session)
    try:
        row = await svc.set_context(track_id, data.content)
    except TrackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info("admin_track_context_set", track_id=track_id)
    return TrackContextResponse.model_validate(row)


@router.delete(
    "/tracks/{track_id}/context",
    response_model=TrackContextResponse,
    summary="[Admin] Clear track context",
)
@limiter.limit("60/minute")
async def admin_clear_track_context(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> TrackContextResponse:
    svc = AdminTrackContextService(session)
    try:
        row = await svc.clear_context(track_id)
    except TrackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info("admin_track_context_cleared", track_id=track_id)
    return TrackContextResponse.model_validate(row)


@router.get(
    "/tracks/{track_id}/prompt",
    response_model=SinglePromptResponse,
    summary="[Admin] Generate copy-ready prompt for one track",
)
@limiter.limit("60/minute")
async def admin_get_track_prompt(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> SinglePromptResponse:
    svc = AdminTrackContextService(session)
    try:
        prompt, lang = await svc.single_prompt(track_id)
    except TrackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    return SinglePromptResponse(prompt=prompt, language=lang)


@router.get(
    "/tracks/{track_id}/upload-meta",
    summary="[Admin] Get upload metadata for a track",
)
@limiter.limit("60/minute")
async def admin_get_upload_meta(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> dict:
    from app.models.upload_meta import TrackUploadMeta

    result = await session.execute(
        select(TrackUploadMeta).where(TrackUploadMeta.track_id == track_id)
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload meta not found",
        )
    return {
        "track_id": meta.track_id,
        "upload_ip": meta.upload_ip,
        "upload_user_agent": meta.upload_user_agent,
        "upload_terms_accepted": (meta.upload_terms_accepted),
        "upload_terms_version": meta.upload_terms_version,
        "upload_telegram_data": meta.upload_telegram_data,
        "created_at": str(meta.created_at),
    }
