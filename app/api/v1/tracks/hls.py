"""HLS adaptive-bitrate streaming endpoints."""

import contextlib

import structlog
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.observability import offline_eligibility_observed
from app.core.rate_limit import limiter
from app.dependencies import get_db, get_optional_user
from app.models.track import Track
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
# Master / variant manifests change rarely (only on re-transcode) but
# clients should still revalidate quickly so a re-transcoded bundle is
# picked up. Sub-minute TTL is cheap because hls.js requests the
# manifest exactly once per session.
_MANIFEST_CACHE_CONTROL = "public, max-age=60"
# CAS segments embed the source SHA-256 in the key — bytes can never
# change for a given URL — so segment responses are safely immutable.
_CAS_SEGMENT_CACHE_CONTROL = "public, max-age=31536000, immutable"
# Legacy non-CAS segments live under ``hls/<track_id>/...`` and could
# be re-transcoded in place. Use a moderate TTL; the SW Cache layer
# still benefits, but we revalidate within the day.
_LEGACY_SEGMENT_CACHE_CONTROL = "public, max-age=86400"


def _segment_cache_control(prefix: str) -> str:
    if prefix.startswith("hls-blobs/"):
        return _CAS_SEGMENT_CACHE_CONTROL
    return _LEGACY_SEGMENT_CACHE_CONTROL


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


def _client_etag_match(
    if_none_match: str | None,
    etag: str | None,
) -> bool:
    if not if_none_match or not etag:
        return False
    target = etag.strip('"')
    candidates = [c.strip().strip('"') for c in if_none_match.split(",")]
    return target in candidates or "*" in candidates


async def _stream_hls_object(
    request: Request,
    key: str,
    media_type: str,
    extra_headers: dict[str, str],
    cache_control: str,
) -> Response:
    """Stream an HLS manifest or segment from S3 to the client.

    Mirrors :func:`playback._stream_s3_audio_object` so segments are
    not buffered in app RAM and conditional GET (``If-None-Match``)
    short-circuits to 304 for the SW Cache layer.
    """
    if_none_match = request.headers.get("if-none-match")
    try:
        meta, body_iter = await s3.open_object_range(key, None)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HLS asset not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="HLS storage error",
        ) from exc

    headers: dict[str, str] = {
        "Cache-Control": cache_control,
    }
    if meta.etag:
        headers["ETag"] = f'"{meta.etag}"'
    headers.update(extra_headers)

    if _client_etag_match(if_none_match, meta.etag):
        with contextlib.suppress(BaseException):
            await body_iter.aclose()
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=headers,
        )

    headers["Content-Length"] = str(meta.content_length)
    return StreamingResponse(
        body_iter,
        status_code=status.HTTP_200_OK,
        media_type=media_type,
        headers=headers,
    )


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
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HLS not ready for this track",
        )
    from app.services.ugc_playback_normalize_service import (
        maybe_schedule_ugc_playback_normalize,
    )

    if not track.hls_manifest_key:
        await maybe_schedule_ugc_playback_normalize(
            session,
            track,
            trigger="hls_not_ready",
        )
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
    try:
        return await _stream_hls_object(
            request,
            track.hls_manifest_key,
            media_type=_HLS_MIME,
            extra_headers=_offline_header(track),
            cache_control=_MANIFEST_CACHE_CONTROL,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            await maybe_schedule_ugc_playback_normalize(
                session,
                track,
                trigger="hls_master_missing",
            )
            await _clear_stale_hls_manifest(track_id, track.hls_manifest_key)
        raise


async def _clear_stale_hls_manifest(
    track_id: int,
    expected_key: str,
) -> None:
    """Best-effort: drop a dangling ``hls_manifest_key`` so the next
    play falls back to progressive without a fresh round-trip through
    the broken bundle.
    """
    try:
        async with AsyncSessionLocal() as session:
            t = await session.get(Track, track_id)
            if t is None or t.hls_manifest_key != expected_key:
                return
            t.hls_manifest_key = None
            await session.commit()
            logger.warning(
                "hls_manifest_key_cleared_on_404",
                track_id=track_id,
                manifest_key=expected_key,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "hls_manifest_key_cleanup_failed",
            track_id=track_id,
            error=str(exc),
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
    structlog.contextvars.bind_contextvars(track_id=track_id, variant=variant)
    if variant not in _VALID_VARIANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid variant — use 'hi' or 'lo'",
        )
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if not track or not track.is_active or not track.is_public:
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
    return await _stream_hls_object(
        request,
        key,
        media_type=_HLS_MIME,
        extra_headers=_offline_header(track),
        cache_control=_MANIFEST_CACHE_CONTROL,
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
    if not track or not track.is_active or not track.is_public:
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
    return await _stream_hls_object(
        request,
        key,
        media_type=_TS_MIME,
        extra_headers=_offline_header(track),
        cache_control=_segment_cache_control(prefix),
    )
