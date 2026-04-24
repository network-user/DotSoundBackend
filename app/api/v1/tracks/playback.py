"""Track playback endpoints — stream URL, play count, cover, single track."""

import structlog
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, get_optional_user
from app.models.user import User
from app.repositories.track import TrackRepository
from app.schemas.card import TrackCardResponse
from app.schemas.share import ShareResponse
from app.schemas.track import (
    AdjacentTracksResponse,
    PlaybackMode,
    PlayResponse,
    StreamResponse,
    TrackQueueResponse,
    TrackResponse,
)
from app.services.card_service import CardService
from app.services.search_playcount_drain import (
    mark_playcount_dirty_async,
)
from app.services.track_service import TrackService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _stream_ttl(source_platform: str | None) -> int:
    if source_platform == "youtube":
        return 21600  # ~6 hours
    if source_platform == "bandcamp":
        return 3600   # ~1 hour
    return 300        # SoundCloud default


async def _resolve_third_party_stream(
    track: object,
    session: object,
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
        return await sc_service.get_stream_info(track.sc_url)  # type: ignore[attr-defined]

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
    if current_user and getattr(track, "uploaded_by_id", None) == current_user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Track not found",
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
        stream_url, protocol = await _resolve_third_party_stream(
            track, session
        )
        return StreamResponse(
            track_id=track_id,
            url=stream_url,
            stream_type="hls" if protocol == "hls" else "direct",
            expires_in=_stream_ttl(track.source_platform),
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
    summary="Increment play count for a track",
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
    found = await repo.increment_play_count(track_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    play_count = (track.play_count or 0) + 1
    await mark_playcount_dirty_async(track_id)
    logger.info(
        "play_count_updated",
        track_id=track_id,
        play_count=play_count,
    )
    return PlayResponse(track_id=track_id, play_count=play_count)


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

    # Prefer HLS adaptive streaming when available
    if track.hls_manifest_key:
        return RedirectResponse(
            url=f"/api/v1/tracks/{track_id}/hls/master.m3u8",
            status_code=302,
        )

    if track.access_mode == "third_party_stream":
        stream_url, _ = await _resolve_third_party_stream(
            track, session
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
            await s3.download_object_range(
                track.file_key, range_header
            )
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
        return AdjacentTracksResponse(
            prev_id=track_id, next_id=track_id
        )

    if mode == PlaybackMode.shuffle:
        rand_prev = await repo.get_random_id(track_id)
        rand_next = await repo.get_random_id(track_id)
        return AdjacentTracksResponse(
            prev_id=rand_prev, next_id=rand_next
        )

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
    tracks = await repo.get_next_tracks(
        track_id, count
    )
    return TrackQueueResponse(
        next_tracks=[
            TrackResponse.model_validate(t)
            for t in tracks
        ]
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
    web_url = f"{mini_app_url}/track/{track_id}" if mini_app_url else f"/api/v1/tracks/{track_id}"
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
        data = await s3.download_object(
            track.video_key
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found",
        )
    ct = "video/mp4"
    if track.video_key.endswith(".webm"):
        ct = "video/webm"
    return Response(
        content=data,
        media_type=ct,
        headers={
            "Cache-Control": "public, max-age=3600"
        },
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
    return TrackResponse.model_validate(track)
