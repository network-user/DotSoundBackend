"""Track playback endpoints — stream URL, play count, cover, single track."""

from collections.abc import AsyncIterator

import httpx
import structlog
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.user import User
from app.repositories.track import TrackRepository
from app.schemas.card import TrackCardResponse
from app.schemas.share import ShareResponse
from app.schemas.snippet import SnippetCreateRequest, SnippetOut
from app.schemas.track import (
    AdjacentTracksResponse,
    PlaybackMode,
    PlayResponse,
    RadioTrackQueueResponse,
    StreamResponse,
    TrackQueueResponse,
    TrackResponse,
)
from app.services.card_service import CardService
from app.services.public_playcount_service import (
    PublicPlayCountService,
)
from app.services.radio_service import RadioService
from app.services.snippet_service import SnippetService
from app.services.track_response_build import (
    build_track_response,
    build_track_responses,
)
from app.services.track_service import TrackService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _stream_ttl(source_platform: str | None) -> int:
    if source_platform == "youtube":
        return 21600  # ~6 hours
    if source_platform == "bandcamp":
        return 3600  # ~1 hour
    return 300  # SoundCloud default


def _third_party_is_soundcloud(tr: object) -> bool:
    pf = getattr(tr, "source_platform", None)
    return pf == "soundcloud" or bool(
        not pf and getattr(tr, "sc_url", None),
    )


async def _resolve_third_party_stream(
    track: object,
    session: object,
    *,
    use_cache: bool = True,
) -> tuple[str, str]:
    platform: str | None = getattr(track, "source_platform", None)

    if platform == "soundcloud" or (
        not platform and getattr(track, "sc_url", None)
    ):
        if not getattr(track, "sc_url", None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SC track missing URL",
            )
        from app.config import settings
        from app.services.soundcloud_service import SoundCloudService

        sc_service = SoundCloudService(settings.sc_client_id, session)  # type: ignore[arg-type]
        return await sc_service.get_stream_info(track.sc_url, use_cache=use_cache)  # type: ignore[attr-defined]

    if platform == "youtube":
        src: str | None = getattr(track, "source_url", None)
        if not src:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="YouTube track missing source URL",
            )
        from app.services.youtube_service import YouTubeService

        yt_service = YouTubeService(session)  # type: ignore[arg-type]
        return await yt_service.get_stream_info(src)

    if platform == "bandcamp":
        src = getattr(track, "source_url", None)
        if not src:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Bandcamp track missing source URL",
            )
        from app.services.bandcamp_service import BandcampService

        bc_service = BandcampService(session)  # type: ignore[arg-type]
        return await bc_service.get_stream_info(src)

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown stream platform: {platform!r}",
    )


def _check_access(track: object, current_user: User | None = None) -> None:
    if getattr(track, "is_public", True):
        return
    if (
        current_user
        and getattr(track, "uploaded_by_id", None) == current_user.id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Track not found",
    )


async def _http_proxy_range_get(
    request: Request,
    stream_url: str,
    *,
    detail_fail: str,
    detail_error: str,
    extra_headers: dict[str, str] | None = None,
) -> StreamingResponse:
    """Proxy GET + Range: media is same-origin for WebAudio + ``<audio>``."""
    from app.config import settings

    range_header: str | None = request.headers.get("range")
    h: dict[str, str] = {
        "User-Agent": settings.outbound_user_agent,
    }
    if extra_headers:
        h.update(extra_headers)
    if range_header:
        h["Range"] = range_header

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(300.0, connect=30.0),
        follow_redirects=True,
    )
    try:
        req = client.build_request("GET", stream_url, headers=h)
        resp = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_error,
        ) from exc

    if resp.status_code not in (200, 206):
        body_preview = b""
        try:
            body_preview = await resp.aread()
        except Exception:
            pass
        await resp.aclose()
        await client.aclose()
        logger.warning(
            "proxy_upstream_error",
            upstream_status=resp.status_code,
            url_host=(
                stream_url.split("://", 1)[-1].split("/", 1)[0]
                if "://" in stream_url
                else "?"
            ),
            body_preview=body_preview[:200].decode("utf-8", errors="replace"),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_fail,
        )

    out_h: dict[str, str] = {
        "Accept-Ranges": resp.headers.get("accept-ranges", "bytes"),
    }
    if ct := resp.headers.get("content-type"):
        out_h["Content-Type"] = ct
    if cl := resp.headers.get("content-length"):
        out_h["Content-Length"] = cl
    if cr := resp.headers.get("content-range"):
        out_h["Content-Range"] = cr

    async def body_iter() -> AsyncIterator[bytes]:
        try:
            async for chunk in resp.aiter_bytes(65536):
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        body_iter(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "audio/mpeg"),
        headers=out_h,
    )


async def _proxy_cors_bypass_third_party_audio(
    request: Request,
    track: object,
    session: AsyncSession,
) -> StreamingResponse:
    """CDNs (YouTube, Bandcamp) do not allow CORS for this player setup."""
    sp = getattr(track, "source_platform", None)
    if sp == "bandcamp":
        from app.services.bandcamp_service import BandcampService

        src: str | None = getattr(track, "source_url", None)
        if not src:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Bandcamp track missing source URL",
            )
        bc = BandcampService(session)
        stream_url, _ = await bc.get_stream_info(src)
        return await _http_proxy_range_get(
            request,
            stream_url,
            detail_fail="Bandcamp stream failed",
            detail_error="Bandcamp stream error",
        )
    if sp == "youtube":
        from app.services.youtube_service import YouTubeService

        yu: str | None = getattr(track, "source_url", None)
        if not yu:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="YouTube track missing source URL",
            )
        ys = YouTubeService(session)
        stream_url, _ = await ys.get_stream_info(yu)
        return await _http_proxy_range_get(
            request,
            stream_url,
            detail_fail="YouTube stream failed",
            detail_error="YouTube stream error",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="proxy only for bandcamp or youtube",
    )


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
    current_user: User | None = Depends(get_optional_user),
) -> StreamResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    if track.access_mode == "third_party_stream":
        spf = getattr(track, "source_platform", None)
        if spf == "youtube" and not settings.youtube_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "YouTube playback is temporarily disabled. "
                    "Set YOUTUBE_ENABLED=true once a proxy pool is configured."
                ),
            )
        if spf in ("bandcamp", "youtube"):
            return StreamResponse(
                track_id=track_id,
                url=f"/api/v1/tracks/{track_id}/audio",
                stream_type="direct",
                expires_in=_stream_ttl(
                    "bandcamp" if spf == "bandcamp" else "youtube"
                ),
            )
        stream_track_id = track_id
        stream_pf = track.source_platform
        eff_track: object = track
        try:
            stream_url, protocol = await _resolve_third_party_stream(
                eff_track, session
            )
        except HTTPException as exc:
            if exc.status_code in (403, 404, 410, 503):
                from app.config import settings as _settings
                from app.services.track_fallback_service import (
                    TrackFallbackService,
                )

                fallback_svc = TrackFallbackService(session, _settings)
                replacement = await fallback_svc.find_and_apply_fallback(
                    track
                )
                if replacement:
                    eff_track = replacement
                    stream_url, protocol = await _resolve_third_party_stream(
                        replacement, session
                    )
                    stream_track_id = replacement.id
                    stream_pf = replacement.source_platform
                else:
                    raise
            else:
                raise
        if protocol == "hls" or not _third_party_is_soundcloud(
            eff_track,
        ):
            return StreamResponse(
                track_id=stream_track_id,
                url=stream_url,
                stream_type="hls" if protocol == "hls" else "direct",
                expires_in=_stream_ttl(stream_pf),
            )
        return StreamResponse(
            track_id=stream_track_id,
            url=f"/api/v1/tracks/{stream_track_id}/audio",
            stream_type="direct",
            expires_in=_stream_ttl(stream_pf),
        )
    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file",
        )
    url = await s3.get_presigned_url(track.file_key)
    logger.info("stream_url_generated", track_id=track_id)
    return StreamResponse(
        track_id=track_id,
        url=url,
        stream_type="direct",
    )


@router.post(
    "/{track_id}/play",
    response_model=PlayResponse,
    summary="Play count: guests may bump; signed-in from listen",
)
@limiter.limit("20/minute")
async def play_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> PlayResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if not track or not track.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    if current_user is not None:
        fresh = await repo.get_by_id(track_id)
        if not fresh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        return PlayResponse(
            track_id=track_id,
            play_count=fresh.play_count or 0,
        )
    client_ip = request.client.host if request.client else ""
    guest_svc = PublicPlayCountService(session)
    updated = await guest_svc.bump_guest_from_play(track_id, client_ip)
    if updated is not None:
        return PlayResponse(track_id=track_id, play_count=updated)
    fresh = await repo.get_by_id(track_id)
    if not fresh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    return PlayResponse(track_id=track_id, play_count=fresh.play_count or 0)


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
    current_user: User | None = Depends(get_optional_user),
) -> StreamResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track or not track.cover_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover not found",
        )
    _check_access(track, current_user)
    url = await s3.get_presigned_url(track.cover_key)
    return StreamResponse(track_id=track_id, url=url)


@router.get(
    "/{track_id}/audio",
    summary="Proxy-stream audio with HTTP Range support",
    response_model=None,
)
@limiter.limit("120/minute")
async def audio_stream(
    request: Request,
    track_id: int,
    force_progressive: bool = Query(
        False,
        description=(
            "If true, never redirect to HLS; stream the stored file "
            "(e.g. MP3) with Range. Use when MSE/HLS failed and the "
            "client needs a plain progressive URL."
        ),
    ),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> StreamingResponse | RedirectResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)

    if track.hls_manifest_key and not force_progressive:
        return RedirectResponse(
            url=f"/api/v1/tracks/{track_id}/hls/master.m3u8",
            status_code=302,
        )

    if track.access_mode == "third_party_stream":
        if getattr(track, "source_platform", None) in ("bandcamp", "youtube"):
            return await _proxy_cors_bypass_third_party_audio(
                request, track, session
            )
        stream_url, protocol = await _resolve_third_party_stream(
            track, session, use_cache=not _third_party_is_soundcloud(track)
        )
        if _third_party_is_soundcloud(track) and protocol != "hls":
            return await _http_proxy_range_get(
                request,
                stream_url,
                detail_fail="SoundCloud stream failed",
                detail_error="SoundCloud stream error",
                extra_headers={
                    "User-Agent": settings.lyrics_sc_cdn_user_agent,
                    "Referer": settings.lyrics_sc_cdn_referer,
                },
            )
        return RedirectResponse(url=stream_url, status_code=302)

    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file",
        )

    range_header = request.headers.get("range")
    try:
        data, content_length, content_range, content_type = (
            await s3.download_object_range(track.file_key, range_header)
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "NoSuchKey":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio file not found in storage",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage error",
        ) from exc

    http_status = 206 if content_range else 200
    headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }
    if content_range:
        headers["Content-Range"] = content_range
    logger.info(
        "audio_stream_started",
        track_id=track_id,
        range=range_header,
        status=http_status,
    )
    return Response(
        content=data,
        status_code=http_status,
        media_type=content_type,
        headers=headers,
    )


@router.get(
    "/{track_id}/adjacent",
    response_model=AdjacentTracksResponse,
    summary="Get prev/next track IDs for navigation",
)
@limiter.limit("300/minute")
async def get_adjacent_tracks(
    request: Request,
    track_id: int,
    mode: PlaybackMode = Query(PlaybackMode.sequential),
    session: AsyncSession = Depends(get_db),
) -> AdjacentTracksResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if not track or not track.is_active or not track.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    if mode == PlaybackMode.repeat_one:
        return AdjacentTracksResponse(prev_id=track_id, next_id=track_id)

    if mode == PlaybackMode.shuffle:
        rand_prev = await repo.get_random_id(track_id)
        rand_next = await repo.get_random_id(track_id)
        return AdjacentTracksResponse(prev_id=rand_prev, next_id=rand_next)

    prev_id, next_id = await repo.get_adjacent(track_id)
    return AdjacentTracksResponse(prev_id=prev_id, next_id=next_id)


@router.get(
    "/{track_id}/queue",
    response_model=TrackQueueResponse,
    summary="Get next tracks for prefetch",
)
@limiter.limit("120/minute")
async def get_track_queue(
    request: Request,
    track_id: int,
    count: int = Query(3, ge=1, le=10),
    session: AsyncSession = Depends(get_db),
) -> TrackQueueResponse:
    repo = TrackRepository(session)
    tracks = await repo.get_next_tracks(track_id, count)
    return TrackQueueResponse(
        next_tracks=await build_track_responses(session, tracks),
    )


@router.get(
    "/{track_id}/radio",
    response_model=RadioTrackQueueResponse,
    summary="Get radio queue from seed (catalog + optional upstream mix)",
)
@limiter.limit("60/minute")
async def get_radio_queue(
    request: Request,
    track_id: int,
    count: int = Query(3, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> RadioTrackQueueResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    repo = TrackRepository(session)
    track = await repo.get_by_id(track_id)
    if not track or not track.is_active or not track.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    rsvc = RadioService(session, settings)
    nxt, src = await rsvc.build_queue(track, count, current_user)
    return RadioTrackQueueResponse(
        next_tracks=await build_track_responses(session, nxt),
        source=src,
    )


@router.post(
    "/{track_id}/snippets",
    response_model=SnippetOut,
    summary="Request a short UGC audio snippet (async transcode)",
)
@limiter.limit("20/minute")
async def post_track_snippet(
    request: Request,
    track_id: int,
    body: SnippetCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SnippetOut:
    svc = SnippetService(session)
    sn = await svc.request_snippet(
        track_id, current_user, body.start_ms, body.end_ms
    )
    return SnippetOut(
        id=sn.id,
        track_id=sn.track_id,
        status=sn.status,
        file_key=sn.file_key,
        start_ms=sn.start_ms,
        end_ms=sn.end_ms,
        error_message=sn.error_message,
        created_at=sn.created_at,
    )


@router.get(
    "/{track_id}/card",
    response_model=TrackCardResponse,
    summary="Get full track card (track info + author + album + has_lyrics)",
)
@limiter.limit("300/minute")
async def get_track_card(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> TrackCardResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = CardService(session)
    card = await service.get_card(
        track_id,
        requester_id=current_user.id if current_user else None,
    )
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    return card


@router.get(
    "/{track_id}/share",
    response_model=ShareResponse,
    summary="Get shareable links for a track",
)
@limiter.limit("120/minute")
async def get_share_links(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ShareResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    from app.config import settings

    mini_app_url = settings.mini_app_url or ""
    bot_username = settings.telegram_bot_username or ""
    web_url = (
        f"{mini_app_url}/track/{track_id}"
        if mini_app_url
        else f"/api/v1/tracks/{track_id}"
    )
    tg_url = (
        f"https://t.me/{bot_username}/app?startapp=track_{track_id}"
        if bot_username
        else f"https://t.me/share/url?url={web_url}"
    )
    return ShareResponse(
        track_id=track_id,
        url=web_url,
        telegram_share_url=tg_url,
    )


@router.get(
    "/{track_id}/video",
    response_model=None,
)
@limiter.limit("120/minute")
async def video_proxy(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> Response:
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track or not track.video_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    _check_access(track, current_user)
    try:
        data = await s3.download_object(track.video_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found",
        ) from None
    ct = "video/mp4"
    if track.video_key.endswith(".webm"):
        ct = "video/webm"
    return Response(
        content=data,
        media_type=ct,
        headers={"Cache-Control": "public, max-age=3600"},
    )


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
    current_user: User | None = Depends(get_optional_user),
) -> TrackResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    return await build_track_response(session, track)
