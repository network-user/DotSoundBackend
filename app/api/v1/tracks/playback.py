"""Track playback endpoints — stream URL, play count, cover, single track."""

import contextlib
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from email.utils import formatdate
from typing import Any

import httpx
import structlog
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.core.observability import offline_eligibility_observed
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.track import Track
from app.models.user import User
from app.repositories.track import TrackRepository
from app.schemas.card import TrackCardResponse
from app.schemas.offline import (
    OfflineEligibilityBatchItem,
    OfflineEligibilityBatchRequest,
    OfflineEligibilityBatchResponse,
    OfflineEligibilityResponse,
)
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
from app.services.streaming_egress_pool import make_sticky_key
from app.services.track_playback_health_service import (
    TrackPlaybackHealthService,
    playback_suppressed_blocks_streaming,
)
from app.services.track_response_build import (
    build_track_response,
    build_track_responses,
)
from app.services.track_service import TrackService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _http_exc_detail(exc: HTTPException) -> str:
    return _detail_to_text(exc.detail)


def _detail_to_text(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(detail)


def _http_exc_message(exc: HTTPException) -> str:
    d = exc.detail
    if isinstance(d, dict):
        msg = d.get("message")
        if isinstance(msg, str) and msg:
            return msg
        code = d.get("code")
        if isinstance(code, str) and code:
            return code
    return d if isinstance(d, str) else str(d)


_SC_USER_MESSAGES_RU: dict[str, str] = {
    "geo_blocked": (
        "Этот трек заблокирован правообладателем для "
        "воспроизведения в нашем регионе."
    ),
    "subscription_required": (
        "Этот трек доступен только подписчикам SoundCloud Go+."
    ),
    "preview_only": (
        "На SoundCloud доступна только короткая превью-версия " "этого трека."
    ),
    "snippet_only": (
        "SoundCloud отдаёт для этого трека только короткий "
        "сниппет — полная версия недоступна."
    ),
    "removed": ("Этот трек удалён или скрыт на SoundCloud."),
    "not_streamable": (
        "Этот трек на SoundCloud отключён для потокового " "воспроизведения."
    ),
    "no_playable_transcoding": (
        "У этого трека нет ни одного потокового формата, "
        "доступного для воспроизведения."
    ),
    "provider_manifest_not_found_for_all_formats": (
        "SoundCloud сейчас не отдаёт ни один поток для этого "
        "трека. Возможно, он стал недоступен в нашем регионе."
    ),
    "provider_returned_no_playable_url": (
        "У этого трека нет потоков, которые мы могли бы " "воспроизвести."
    ),
    "encrypted_hls_unsupported": (
        "SoundCloud отдаёт этот трек только в защищённом HLS-формате, "
        "который DotSound пока не воспроизводит. Откройте трек на "
        "SoundCloud или выберите другой источник."
    ),
}


def _third_party_error_detail(
    exc: HTTPException,
    track: object,
    track_id: int,
) -> dict[str, Any]:
    detail = dict(exc.detail) if isinstance(exc.detail, dict) else {}
    detail.setdefault("message", _http_exc_message(exc))
    detail.setdefault("code", "third_party_stream_error")
    detail.setdefault("reason", "stream_resolution_failed")
    detail.setdefault("retryable", exc.status_code in (502, 503, 504))
    detail["http_status"] = exc.status_code
    detail["track_id"] = track_id
    detail["access_mode"] = getattr(track, "access_mode", None)
    detail["catalog_type"] = getattr(track, "catalog_type", None)
    detail["source_platform"] = getattr(track, "source_platform", None)
    if _third_party_is_soundcloud(track):
        detail.setdefault("provider", "soundcloud")
        reason_for_msg = detail.get("reason")
        user_message = (
            _SC_USER_MESSAGES_RU.get(str(reason_for_msg))
            if isinstance(reason_for_msg, str)
            else None
        )
        if user_message:
            detail.setdefault("user_message", user_message)
    return detail


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
        sc_url = getattr(track, "sc_url", None)
        if not isinstance(sc_url, str) or not sc_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SC track missing URL",
            )
        from app.config import settings
        from app.services.soundcloud_service import SoundCloudService

        sc_service = SoundCloudService(settings.sc_client_id, session)  # type: ignore[arg-type]
        return await sc_service.get_stream_info(
            sc_url,
            prefer_hls=False,
            use_cache=use_cache,
        )

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


_audio_proxy_http_clients: dict[str | None, httpx.AsyncClient] = {}


async def close_audio_proxy_clients() -> None:
    """Close pooled audio-proxy HTTP clients. Called on app shutdown."""
    for c in list(_audio_proxy_http_clients.values()):
        with contextlib.suppress(Exception):
            await c.aclose()
    _audio_proxy_http_clients.clear()


def reset_audio_proxy_clients() -> None:
    """Discard pooled clients so the next request opens fresh connections.

    Called after a Tor NEWNYM signal so new audio streams build new SOCKS5
    tunnels through the rotated circuits.  Active responses keep their
    existing clients — connections close naturally when the stream ends.
    """
    _audio_proxy_http_clients.clear()


def _get_audio_proxy_client(proxy_url: str | None) -> httpx.AsyncClient:
    """Return a pooled AsyncClient for the given proxy URL.

    Reuses an existing client so the underlying TCP/TLS connections
    (and SOCKS5 tunnel for Tor/static proxies) are shared across
    requests instead of being re-negotiated on every audio stream.
    """
    client = _audio_proxy_http_clients.get(proxy_url)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=30.0),
            follow_redirects=True,
            trust_env=False,
            proxy=proxy_url,
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
            ),
        )
        _audio_proxy_http_clients[proxy_url] = client
    return client


async def _http_proxy_range_get(
    request: Request,
    stream_url: str,
    *,
    detail_fail: str,
    detail_error: str,
    extra_headers: dict[str, str] | None = None,
    proxy_service: str | None = None,
    sticky_key: str | None = None,
) -> StreamingResponse:
    """Proxy GET + Range: media is same-origin for WebAudio + ``<audio>``.

    Egress selection logic:
    - When ``proxy_service`` is a third-party audio CDN streaming
      service (SoundCloud / Bandcamp / YouTube), we go through the
      dedicated streaming egress pool — server's native IP by
      default, with optional ``STREAMING_PROXY_OUT_URLS`` round-robin
      and per-track sticky binding. Tor is never consulted here:
      Tor exits are consistently throttled by SC's audio CDN and
      caused the "track plays once, then 502s" pattern.
    - For any other ``proxy_service`` the call stays on the legacy
      ``OUTBOUND_STATIC_PROXY_URLS`` / Tor path used by the catalog
      and resolve APIs.
    - When ``proxy_service`` is ``None`` the request goes direct.
    """
    from app.config import settings

    range_header: str | None = request.headers.get("range")
    h: dict[str, str] = {
        "User-Agent": settings.outbound_user_agent,
    }
    if extra_headers:
        h.update(extra_headers)
    if range_header:
        h["Range"] = range_header

    out_proxy: str | None = None
    streaming_decision = None
    if proxy_service:
        from app.services.streaming_egress_pool import (
            get_streaming_egress_pool,
            is_audio_streaming_service,
        )

        if is_audio_streaming_service(proxy_service):
            pool = get_streaming_egress_pool()
            streaming_decision = pool.pick(
                proxy_urls=settings.streaming_proxy_out_urls_list,
                sticky_key=sticky_key,
                allow_direct_fallback=(
                    settings.streaming_proxy_out_fallback_direct
                ),
            )
            if streaming_decision is None:
                logger.warning(
                    "streaming_egress_pool_exhausted",
                    service=proxy_service,
                    sticky_key=sticky_key,
                )
                try:
                    from app.core.observability import (
                        streaming_egress_pool_exhausted,
                    )

                    streaming_egress_pool_exhausted(service=proxy_service)
                except Exception:  # pragma: no cover - metrics best-effort
                    pass
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=detail_error,
                )
            out_proxy = streaming_decision.proxy_url
            logger.info(
                "streaming_egress_pool_selected",
                service=proxy_service,
                egress=streaming_decision.egress_name,
                sticky_key=sticky_key,
                via_proxy=out_proxy is not None,
            )
        else:
            from app.services.outbound_proxy import get_outbound_proxy

            out_proxy = get_outbound_proxy(proxy_service)

    client = _get_audio_proxy_client(out_proxy)
    started_at = time.monotonic()
    try:
        req = client.build_request("GET", stream_url, headers=h)
        resp = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        if proxy_service and streaming_decision is None:
            from app.services.outbound_proxy import (
                record_outbound_proxy_error,
            )

            record_outbound_proxy_error(
                service=proxy_service,
                proxy_url=out_proxy,
                method="GET",
                url=stream_url,
                error=exc,
                started_at=started_at,
            )
        if streaming_decision is not None:
            from app.services.streaming_egress_pool import (
                get_streaming_egress_pool,
            )

            get_streaming_egress_pool().finish(streaming_decision, ok=False)
        elif out_proxy:
            from app.services.outbound_proxy import (
                report_outbound_proxy_result,
            )

            report_outbound_proxy_result(out_proxy, ok=False)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_error,
        ) from exc

    if resp.status_code not in (200, 206):
        if streaming_decision is not None:
            from app.services.streaming_egress_pool import (
                get_streaming_egress_pool,
            )

            get_streaming_egress_pool().finish(streaming_decision, ok=False)
        elif out_proxy:
            from app.services.outbound_proxy import (
                report_outbound_proxy_result,
            )

            report_outbound_proxy_result(out_proxy, ok=False)
        body_preview = b""
        with contextlib.suppress(Exception):
            body_preview = await resp.aread()
        await resp.aclose()
        logger.warning(
            "proxy_upstream_error",
            upstream_status=resp.status_code,
            url_host=(
                stream_url.split("://", 1)[-1].split("/", 1)[0]
                if "://" in stream_url
                else "?"
            ),
            outbound_proxied=bool(out_proxy),
            streaming_egress=(
                streaming_decision.egress_name if streaming_decision else None
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
        upstream_error = False
        try:
            async for chunk in resp.aiter_bytes(65536):
                yield chunk
        except httpx.HTTPError:
            upstream_error = True
            raise
        finally:
            if streaming_decision is not None:
                from app.services.streaming_egress_pool import (
                    get_streaming_egress_pool,
                )

                get_streaming_egress_pool().finish(
                    streaming_decision,
                    ok=not upstream_error,
                )
            elif out_proxy:
                from app.services.outbound_proxy import (
                    report_outbound_proxy_result,
                )

                report_outbound_proxy_result(out_proxy, ok=not upstream_error)
            await resp.aclose()

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
            proxy_service="bandcamp",
            sticky_key=make_sticky_key(
                int(getattr(track, "id", 0)), stream_url
            ),
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
            proxy_service="youtube",
            sticky_key=make_sticky_key(
                int(getattr(track, "id", 0)), stream_url
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="proxy only for bandcamp or youtube",
    )


def _sc_detail_reason_is_manifest_all_404(
    exc: HTTPException,
) -> bool:
    """Return True for SC 502 with all-manifests-404 reason."""
    if exc.status_code != 502:
        return False
    detail = exc.detail if isinstance(exc.detail, dict) else None
    if not detail:
        return False
    return (
        detail.get("reason") == "provider_manifest_not_found_for_all_formats"
    )


def _audio_cache_control(file_key: str) -> str:
    """Cache-Control for an audio S3 key.

    Content-addressed blobs (``blobs/<xx>/<sha256>.<ext>``) are
    immutable by construction: their key embeds the full SHA-256
    of the bytes. We tell shared caches to keep them effectively
    forever. Legacy / per-user keys still get a short cache TTL so
    the browser does not re-pull the same MP3 every track switch
    inside the session.
    """
    if file_key.startswith("blobs/"):
        return "public, max-age=31536000, immutable"
    return "public, max-age=300"


def _format_http_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    try:
        seconds = value.timestamp()
    except (AttributeError, TypeError):
        return None
    return formatdate(seconds, usegmt=True)


def _client_supports_conditional_match(
    if_none_match: str | None,
    etag: str | None,
) -> bool:
    if not if_none_match or not etag:
        return False
    target = etag.strip('"')
    candidates = [c.strip().strip('"') for c in if_none_match.split(",")]
    return target in candidates or "*" in candidates


async def _stream_s3_audio_object(
    request: Request,
    file_key: str,
    extra_headers: dict[str, str],
    *,
    fallback_media_type: str = "audio/mpeg",
) -> Response:
    """Pump an S3 object straight to the client in 64 KiB chunks.

    Uses :func:`s3.open_object_range` so that ``Range`` requests yield
    the first byte to the client roughly as fast as MinIO can give it
    to us — no whole-range buffering in app RAM. Honours
    ``If-None-Match`` for free 304s and applies an immutability-aware
    ``Cache-Control`` so the browser, the SW Cache, and any future
    edge caches all do their job.
    """
    range_header = request.headers.get("range")
    if_none_match = request.headers.get("if-none-match")
    if_modified_since = request.headers.get("if-modified-since")

    try:
        meta, body_iter = await s3.open_object_range(
            file_key,
            range_header,
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

    last_modified_http = _format_http_date(meta.last_modified)

    base_headers: dict[str, str] = {
        "Accept-Ranges": meta.accept_ranges or "bytes",
        "Cache-Control": _audio_cache_control(file_key),
    }
    if meta.etag:
        base_headers["ETag"] = f'"{meta.etag}"'
    if last_modified_http:
        base_headers["Last-Modified"] = last_modified_http
    base_headers.update(extra_headers)

    not_modified = _client_supports_conditional_match(
        if_none_match, meta.etag
    ) or (
        range_header is None
        and if_modified_since is not None
        and last_modified_http == if_modified_since
    )
    if not_modified:
        with contextlib.suppress(BaseException):
            await body_iter.aclose()
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers=base_headers,
        )

    headers = dict(base_headers)
    headers["Content-Length"] = str(meta.content_length)
    if meta.content_range:
        headers["Content-Range"] = meta.content_range

    http_status = (
        status.HTTP_206_PARTIAL_CONTENT
        if meta.content_range
        else status.HTTP_200_OK
    )
    return StreamingResponse(
        body_iter,
        status_code=http_status,
        media_type=meta.content_type or fallback_media_type,
        headers=headers,
    )


async def _resolve_third_party_stream_with_recovery(
    track: Track,
    session: AsyncSession,
    *,
    use_cache: bool = True,
) -> tuple[Track, str, str]:
    eff_track: Track = track
    try:
        stream_url, protocol = await _resolve_third_party_stream(
            eff_track,
            session,
            use_cache=use_cache,
        )
        return eff_track, stream_url, protocol
    except HTTPException as exc:
        # SoundCloud may return 502 when all transcodings are unavailable
        # (e.g. both progressive and HLS manifests return 404). Treat this
        # as recoverable to allow fallback refresh/replacement logic.
        is_sc_502 = exc.status_code == 502 and _third_party_is_soundcloud(
            eff_track
        )
        if exc.status_code not in (403, 404, 410, 503) and not is_sc_502:
            raise

        from app.config import settings as _settings
        from app.services.track_fallback_service import (
            TrackFallbackService,
        )

        fallback_svc = TrackFallbackService(session, _settings)
        resolved = False
        sc_refresh_codes = (404, 410)
        sc_is_manifest_all_404 = (
            is_sc_502 and _sc_detail_reason_is_manifest_all_404(exc)
        )
        if _third_party_is_soundcloud(eff_track) and (
            exc.status_code in sc_refresh_codes or sc_is_manifest_all_404
        ):
            sc_refreshed = await fallback_svc.try_refresh_sc_url(track)
            if sc_refreshed:
                try:
                    stream_url, protocol = await _resolve_third_party_stream(
                        eff_track,
                        session,
                        use_cache=use_cache,
                    )
                    return eff_track, stream_url, protocol
                except HTTPException:
                    resolved = False
                else:
                    resolved = True
        if not resolved:
            replacement = await fallback_svc.find_and_apply_fallback(track)
            if replacement:
                eff_track = replacement
                stream_url, protocol = await _resolve_third_party_stream(
                    replacement,
                    session,
                    use_cache=use_cache,
                )
                return eff_track, stream_url, protocol
        raise


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
    track = await service.get_track_for_playback(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    if playback_suppressed_blocks_streaming(track, current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback temporarily unavailable for this track",
        )
    # Serve from local S3 cache when available — skips external API call.
    if track.audio_cache_status == "cached" and track.file_key:
        url = await s3.get_presigned_url(track.file_key)
        logger.info("stream_url_from_cache", track_id=track_id)
        return StreamResponse(
            track_id=track_id,
            url=url,
            stream_type="direct",
            expires_in=3600,
        )
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
        try:
            eff_track, stream_url, protocol = (
                await _resolve_third_party_stream_with_recovery(
                    track,
                    session,
                    use_cache=True,
                )
            )
        except HTTPException as exc:
            detail = _third_party_error_detail(exc, track, track_id)
            logger.warning(
                "stream_track_third_party_failed",
                track_id=track_id,
                status_code=exc.status_code,
                detail=_detail_to_text(detail),
                source_platform=getattr(track, "source_platform", None),
            )
            ph = TrackPlaybackHealthService(session)
            await ph.record_server_recovery_exhausted(
                track_id=track_id,
                viewer_user_id=(current_user.id if current_user else None),
                http_status=exc.status_code,
                detail=_detail_to_text(detail),
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail=detail,
                headers=exc.headers,
            ) from exc
        stream_track_id = int(getattr(eff_track, "id", track_id))
        stream_pf = getattr(eff_track, "source_platform", None)
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
    if playback_suppressed_blocks_streaming(track, current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback temporarily unavailable for this track",
        )
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
    track = await service.get_track(
        track_id,
        viewer=current_user,
    )
    if not track or not track.cover_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover not found",
        )
    _check_access(track, current_user)
    url = await s3.get_presigned_url(track.cover_key)
    return StreamResponse(track_id=track_id, url=url)


@router.get(
    "/{track_id}/offline-eligibility",
    response_model=OfflineEligibilityResponse,
    summary=("Whether this track may be saved into the local PWA cache"),
)
@limiter.limit("120/minute")
async def offline_eligibility(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> OfflineEligibilityResponse:
    from app.services.offline_policy_adapter import (
        OFFLINE_MAX_TOTAL_BYTES_PER_USER,
        OFFLINE_MAX_TRACK_BYTES,
        is_offline_allowed,
    )

    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track(track_id, viewer=current_user)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    allowed, reason = is_offline_allowed(
        catalog_type=track.catalog_type,
        access_mode=track.access_mode,
        file_size_bytes=track.file_size_bytes,
    )
    offline_eligibility_observed(allowed=allowed, reason=reason)
    logger.info(
        "offline_eligibility_decision",
        track_id=track_id,
        allowed=allowed,
        reason=reason,
        catalog_type=track.catalog_type,
        access_mode=track.access_mode,
        file_size_bytes=track.file_size_bytes,
    )
    return OfflineEligibilityResponse(
        allowed=allowed,
        reason=reason,
        max_track_bytes=OFFLINE_MAX_TRACK_BYTES,
        max_total_bytes_per_user=OFFLINE_MAX_TOTAL_BYTES_PER_USER,
    )


@router.post(
    "/offline-eligibility-batch",
    response_model=OfflineEligibilityBatchResponse,
    summary=("Batch eligibility check for the local PWA cache"),
)
@limiter.limit("60/minute")
async def offline_eligibility_batch(
    request: Request,
    payload: OfflineEligibilityBatchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> OfflineEligibilityBatchResponse:
    from app.services.offline_policy_adapter import (
        OFFLINE_MAX_TOTAL_BYTES_PER_USER,
        OFFLINE_MAX_TRACK_BYTES,
        is_offline_allowed,
    )

    ids: list[int] = []
    seen: set[int] = set()
    for raw in payload.track_ids:
        if raw in seen:
            continue
        seen.add(raw)
        ids.append(raw)

    service = TrackService(session)
    items: dict[str, OfflineEligibilityBatchItem] = {}
    for tid in ids:
        track = await service.get_track(tid, viewer=current_user)
        if not track:
            items[str(tid)] = OfflineEligibilityBatchItem(
                allowed=False,
                reason="not_found",
            )
            offline_eligibility_observed(allowed=False, reason="not_found")
            continue
        try:
            _check_access(track, current_user)
        except HTTPException:
            items[str(tid)] = OfflineEligibilityBatchItem(
                allowed=False,
                reason="forbidden",
            )
            offline_eligibility_observed(allowed=False, reason="forbidden")
            continue
        allowed, reason = is_offline_allowed(
            catalog_type=track.catalog_type,
            access_mode=track.access_mode,
            file_size_bytes=track.file_size_bytes,
        )
        offline_eligibility_observed(allowed=allowed, reason=reason)
        items[str(tid)] = OfflineEligibilityBatchItem(
            allowed=allowed,
            reason=reason,
        )
    return OfflineEligibilityBatchResponse(
        items=items,
        max_track_bytes=OFFLINE_MAX_TRACK_BYTES,
        max_total_bytes_per_user=OFFLINE_MAX_TOTAL_BYTES_PER_USER,
    )


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
) -> Response | StreamingResponse | RedirectResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = TrackService(session)
    track = await service.get_track_for_playback(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    if playback_suppressed_blocks_streaming(track, current_user):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback temporarily unavailable for this track",
        )

    if track.hls_manifest_key and not force_progressive:
        return RedirectResponse(
            url=f"/api/v1/tracks/{track_id}/hls/master.m3u8",
            status_code=302,
        )

    # Serve from local S3 cache when available.
    if (
        track.audio_cache_status == "cached"
        and track.file_key
        and not track.hls_manifest_key
    ):
        from app.services.offline_policy_adapter import (
            is_offline_allowed,
        )

        allowed, _reason = is_offline_allowed(
            catalog_type=track.catalog_type,
            access_mode=track.access_mode,
            file_size_bytes=track.file_size_bytes,
        )
        try:
            return await _stream_s3_audio_object(
                request,
                track.file_key,
                {"X-Offline-Allowed": "1" if allowed else "0"},
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_502_BAD_GATEWAY:
                # Storage transient error — fall through to live proxy.
                pass
            else:
                raise

    if track.access_mode == "third_party_stream":
        try:
            eff_track, stream_url, protocol = (
                await _resolve_third_party_stream_with_recovery(
                    track,
                    session,
                    use_cache=not _third_party_is_soundcloud(track),
                )
            )
        except HTTPException as exc:
            detail = _third_party_error_detail(exc, track, track_id)
            logger.warning(
                "audio_stream_third_party_failed",
                track_id=track_id,
                status_code=exc.status_code,
                detail=_detail_to_text(detail),
                source_platform=getattr(track, "source_platform", None),
            )
            ph = TrackPlaybackHealthService(session)
            await ph.record_server_recovery_exhausted(
                track_id=track_id,
                viewer_user_id=(current_user.id if current_user else None),
                http_status=exc.status_code,
                detail=_detail_to_text(detail),
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail=detail,
                headers=exc.headers,
            ) from exc
        view_uid = current_user.id if current_user else None
        if getattr(eff_track, "source_platform", None) in (
            "bandcamp",
            "youtube",
        ):
            try:
                return await _proxy_cors_bypass_third_party_audio(
                    request,
                    eff_track,
                    session,
                )
            except HTTPException as exc:
                ph = TrackPlaybackHealthService(session)
                await ph.record_server_proxy_upstream(
                    track_id=track_id,
                    viewer_user_id=view_uid,
                    http_status=exc.status_code,
                    detail=_http_exc_detail(exc),
                )
                raise
        if _third_party_is_soundcloud(eff_track) and protocol != "hls":
            try:
                return await _http_proxy_range_get(
                    request,
                    stream_url,
                    detail_fail="SoundCloud stream failed",
                    detail_error="SoundCloud stream error",
                    extra_headers={
                        "User-Agent": settings.lyrics_sc_cdn_user_agent,
                        "Referer": settings.lyrics_sc_cdn_referer,
                    },
                    proxy_service="soundcloud",
                    sticky_key=make_sticky_key(
                        int(getattr(eff_track, "id", track_id)),
                        stream_url,
                    ),
                )
            except HTTPException as exc:
                ph = TrackPlaybackHealthService(session)
                await ph.record_server_proxy_upstream(
                    track_id=track_id,
                    viewer_user_id=view_uid,
                    http_status=exc.status_code,
                    detail=_http_exc_detail(exc),
                )
                raise
        return RedirectResponse(url=stream_url, status_code=302)

    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file",
        )

    from app.services.offline_policy_adapter import (
        is_offline_allowed,
    )

    allowed, _reason = is_offline_allowed(
        catalog_type=track.catalog_type,
        access_mode=track.access_mode,
        file_size_bytes=track.file_size_bytes,
    )
    return await _stream_s3_audio_object(
        request,
        track.file_key,
        {"X-Offline-Allowed": "1" if allowed else "0"},
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
    summary="Get full track card (track info + album + has_lyrics)",
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
    track = await service.get_track(
        track_id,
        viewer=current_user,
    )
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
    track = await service.get_track(
        track_id,
        viewer=current_user,
    )
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
    track = await service.get_track(
        track_id,
        viewer=current_user,
    )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    _check_access(track, current_user)
    return await build_track_response(
        session,
        track,
        viewer_id=current_user.id if current_user else None,
    )
