"""Admin endpoints for track management."""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin
from app.models.track import Track
from app.models.user import User
from app.services.transcoding import transcode_hls_only

from .schemas import AdminTrackListResponse, AdminTrackResponse

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
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminTrackListResponse:
    offset = (page - 1) * size
    result = await session.execute(
        select(Track).order_by(Track.created_at.desc()).offset(offset).limit(size)
    )
    tracks = list(result.scalars().all())

    count_result = await session.execute(
        select(Track).order_by(None)
    )
    total = len(count_result.scalars().all())

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
    result = await session.execute(
        select(Track).where(Track.id == track_id)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if track.source == "internal" and track.file_key:
        try:
            await s3.delete_object(track.file_key)
        except Exception:
            logger.warning(
                "admin_s3_delete_failed",
                track_id=track_id,
                file_key=track.file_key,
            )
    if track.cover_key:
        try:
            await s3.delete_object(track.cover_key)
        except Exception:
            logger.warning(
                "admin_s3_cover_delete_failed",
                track_id=track_id,
                cover_key=track.cover_key,
            )
    await session.delete(track)
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
    result = await session.execute(
        select(Track).where(Track.id == track_id)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    track.is_active = is_active
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
    result = await session.execute(
        select(Track).where(Track.id == track_id)
    )
    track = result.scalar_one_or_none()
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
    background_tasks.add_task(
        transcode_hls_only, track_id, track.file_key
    )
    logger.info("admin_transcode_queued", track_id=track_id)
    return {"queued": True, "track_id": track_id}


@router.post(
    "/tracks/transcode/batch",
    summary="[Admin] Transcode all tracks without HLS to adaptive bitrate",
)
@limiter.limit("2/minute")
async def admin_transcode_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
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
            transcode_hls_only, track.id, track.file_key
        )
    logger.info("admin_transcode_batch_queued", count=len(tracks))
    return {"queued": len(tracks)}
