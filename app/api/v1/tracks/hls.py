"""HLS adaptive-bitrate streaming endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.observability import offline_eligibility_observed
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
_LEGACY_HLS_PREFIX_TEMPLATE = "hls/{track_id}"


def _hls_storage_prefix(track_id: int, manifest_key: str | None) -> str:
    """Resolve the S3 prefix where this track's HLS bundle lives.

    Internal-stream tracks transcoded by ``transcode_full`` with a
    known source SHA-256 land under the content-addressed prefix
    ``hls-blobs/{xx}/{sha}/...``. Older or non-CAS tracks live at
    the legacy ``hls/{track_id}/...`` path. The master playlist
    references variants relatively (``hi/playlist.m3u8``), so the
    variant and segment endpoints must derive the prefix from the
    same ``track.hls_manifest_key`` the master came from -- otherwise
    HLS playback 404s on the very first variant fetch and HLS.js
    falls back to progressive every track switch, killing the
    benefit of HLS entirely.
    """
    if manifest_key and manifest_key.endswith("/master.m3u8"):
        return manifest_key[: -len("/master.m3u8")]
    return _LEGACY_HLS_PREFIX_TEMPLATE.format(track_id=track_id)


def _offline_header(track: object) -> dict[str, str]:
    """Compute ``X-Offline-Allowed`` for the Service Worker.

    The SW reads this header to decide whether to keep the
    response in the local audio cache. Header value is ``"1"``
    when the track is allowed to be cached, ``"0"`` otherwise.
    """
    from app.services.offline_policy_adapter import (
        is_offline_allowed,
    )

    catalog_type = getattr(track, "catalog_type", "") or ""
    access_mode = getattr(track, "access_mode", "") or ""
    file_size_bytes = getattr(track, "file_size_bytes", None)
    allowed, reason = is_offline_allowed(
        catalog_type=catalog_type,
        access_mode=access_mode,
        file_size_bytes=file_size_bytes,
    )
    offline_eligibility_observed(allowed=allowed, reason=reason)
    return {"X-Offline-Allowed": "1" if allowed else "0"}


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
        headers={
            "Cache-Control": "no-cache",
            **_offline_header(track),
        },
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
    prefix = _hls_storage_prefix(track_id, track.hls_manifest_key)
    key = f"{prefix}/{variant}/playlist.m3u8"
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
        headers={
            "Cache-Control": "no-cache",
            **_offline_header(track),
        },
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
    prefix = _hls_storage_prefix(track_id, track.hls_manifest_key)
    key = f"{prefix}/{variant}/{segment}"
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
        headers={
            "Cache-Control": "max-age=86400",
            **_offline_header(track),
        },
    )
