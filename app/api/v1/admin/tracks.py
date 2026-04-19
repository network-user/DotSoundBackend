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
from app.dependencies import get_db, require_admin
from app.models.user import User
from app.services.admin_service import AdminService
from app.services.transcoding import transcode_hls_only

from .schemas import (
    AdminTrackListResponse,
    AdminTrackResponse,
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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
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
    _admin: User = Depends(require_admin),
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


@router.get(
    "/tracks/{track_id}/upload-meta",
    summary="[Admin] Get upload metadata for a track",
)
@limiter.limit("60/minute")
async def admin_get_upload_meta(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
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
