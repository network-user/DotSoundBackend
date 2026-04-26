from __future__ import annotations

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.tracks.playback import _check_access
from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, get_optional_user
from app.models.user import User
from app.services.genre_samples_service import GenreSamplesService
from app.services.track_preview_transcode import (
    transcode_http_audio_to_fmp4_aac,
)
from app.services.track_service import TrackService

router = APIRouter(prefix="/track-preview", tags=["track-preview"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "/{track_id}/segment.mp4",
    summary="15s AAC preview (fMP4) from stored clip metadata",
)
@limiter.limit("60/minute")
async def get_preview_segment(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> Response:
    structlog.contextvars.bind_contextvars(
        track_id=track_id,
    )
    track_svc = TrackService(session)
    track = await track_svc.get_track(track_id)
    if not track or not track.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file",
        )
    _check_access(track, current_user)
    gs = GenreSamplesService(session)
    try:
        clip = await gs.ensure_preview_clip(track_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    try:
        url = await s3.get_presigned_url(track.file_key)
    except Exception as exc:
        logger.exception("track_preview_presign_failed", exc=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage error",
        ) from exc
    try:
        body = await transcode_http_audio_to_fmp4_aac(
            url,
            clip.start_sec,
            clip.duration_sec,
        )
    except (RuntimeError, OSError, TimeoutError) as exc:
        logger.exception("track_preview_transcode_failed", exc=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Preview transcode failed",
        ) from exc
    return Response(
        content=body,
        media_type="audio/mp4",
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )
