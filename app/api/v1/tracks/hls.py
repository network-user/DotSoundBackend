"""HLS adaptive-bitrate streaming endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, get_optional_user
from app.models.user import User
from app.repositories.track import TrackRepository
from app.services.track_playback_health_service import (
    playback_suppressed_blocks_streaming,
)

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_HLS_MIME = "application/vnd.apple.mpegurl"
_TS_MIME = "video/MP2T"
_VALID_VARIANTS = frozenset({"hi", "lo"})


@router.get(
    "/{track_id}/hls/master.m3u8",
    summary="HLS master playlist (adaptive bitrate)",
)
@limiter.limit("600/minute")
async def hls_master(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> Response:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if not track or not track.hls_manifest_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HLS not ready for this track",
        )
    if not track.is_active or not track.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not available",
        )
    if playback_suppressed_blocks_streaming(track, current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback temporarily unavailable for this track",
        )
    data = await s3.download_object(track.hls_manifest_key)
    return Response(
        content=data,
        media_type=_HLS_MIME,
        headers={"Cache-Control": "no-cache"},
    )


@router.get(
    "/{track_id}/hls/{variant}/playlist.m3u8",
    summary="HLS variant playlist",
)
@limiter.limit("600/minute")
async def hls_variant_playlist(
    request: Request,
    track_id: int,
    variant: str,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> Response:
    structlog.contextvars.bind_contextvars(
        track_id=track_id, variant=variant
    )
    if variant not in _VALID_VARIANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid variant — use 'hi' or 'lo'",
        )
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if (
        not track
        or not track.is_active
        or not track.is_public
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not available",
        )
    if playback_suppressed_blocks_streaming(track, current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback temporarily unavailable for this track",
        )
    key = f"hls/{track_id}/{variant}/playlist.m3u8"
    try:
        data = await s3.download_object(key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )
    return Response(
        content=data,
        media_type=_HLS_MIME,
        headers={"Cache-Control": "no-cache"},
    )


@router.get(
    "/{track_id}/hls/{variant}/{segment}",
    summary="HLS TS segment",
)
@limiter.limit("1200/minute")
async def hls_segment(
    request: Request,
    track_id: int,
    variant: str,
    segment: str,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> Response:
    structlog.contextvars.bind_contextvars(
        track_id=track_id, variant=variant, segment=segment
    )
    if variant not in _VALID_VARIANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid variant",
        )
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if (
        not track
        or not track.is_active
        or not track.is_public
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not available",
        )
    if playback_suppressed_blocks_streaming(track, current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback temporarily unavailable for this track",
        )
    if not segment.endswith(".ts") or not segment[:-3].isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment name",
        )
    key = f"hls/{track_id}/{variant}/{segment}"
    try:
        data = await s3.download_object(key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found",
        )
    return Response(
        content=data,
        media_type=_TS_MIME,
        headers={"Cache-Control": "max-age=86400"},
    )
