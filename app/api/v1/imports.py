from typing import Any

import structlog
from dotsound_private_core.services import (
    is_allowed_vk_music_url,
    normalize_vk_music_url,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.import_service import ImportService
from app.services.linked_account_service import LinkedAccountService
from app.utils.soundcloud_playlist_url import (
    resolve_public_soundcloud_playlist_url,
)
from app.utils.spotify_import_url import is_open_spotify_playlist_or_album_url

router = APIRouter(prefix="/import", tags=["import"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ImportStartRequest(BaseModel):
    track_indices: list[int]


class AccountImportRequest(BaseModel):
    """Import from a connected provider account.

    ``source`` can be:
    - ``"liked"``  — all saved / liked tracks from the account (default)
    - ``"playlist"`` — a specific playlist; requires ``playlist_id``

    Use ``GET /linked-accounts/{provider}/playlists`` to get the list of
    available playlists before requesting a playlist import.
    """

    source: str = "liked"
    playlist_id: str | None = None


class YandexMusicImportRequest(BaseModel):
    url: str = Field(..., min_length=1)


class VkMusicImportRequest(BaseModel):
    url: str = Field(..., min_length=1)


class SoundCloudPlaylistImportRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=4096)


class SpotifyImportRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=4096)


class ImportJobResponse(BaseModel):
    id: int
    source: str
    status: str
    total_tracks: int
    completed_tracks: int
    failed_tracks: int
    tracks_data: dict[str, Any] | None = None
    queue_position: int | None = None

    class Config:
        from_attributes = True


@router.post(
    "/telegram",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def scan_telegram_profile(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.scan_telegram_profile(current_user.id)
    return ImportJobResponse.model_validate(job)


@router.post(
    "/yandex_music",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def scan_yandex_music(
    request: Request,
    body: YandexMusicImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    if not body.url.startswith(
        ("https://music.yandex.ru/", "http://music.yandex.ru/")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("URL must be a music.yandex.ru playlist or " "album link"),
        )
    service = ImportService(session)
    job = await service.scan_external_playlist(
        user_id=current_user.id,
        source="yandex_music",
        url=body.url,
    )
    return ImportJobResponse.model_validate(job)


@router.post(
    "/vk_music",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def scan_vk_music(
    request: Request,
    body: VkMusicImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    norm = normalize_vk_music_url(body.url)
    if not is_allowed_vk_music_url(norm):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "URL must be an official VK (vk.com or vk.ru) "
                "music or playlist link"
            ),
        )
    service = ImportService(session)
    job = await service.scan_external_playlist(
        user_id=current_user.id,
        source="vk_music",
        url=norm,
    )
    return ImportJobResponse.model_validate(job)


@router.post(
    "/soundcloud_playlist",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def scan_soundcloud_playlist(
    request: Request,
    body: SoundCloudPlaylistImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    try:
        normalized = await resolve_public_soundcloud_playlist_url(
            body.url
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Invalid SoundCloud playlist URL",
        ) from exc
    service = ImportService(session)
    job = await service.scan_external_playlist(
        user_id=current_user.id,
        source="soundcloud_playlist",
        url=normalized,
    )
    return ImportJobResponse.model_validate(job)


@router.post(
    "/spotify",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def scan_spotify(
    request: Request,
    body: SpotifyImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    if not is_open_spotify_playlist_or_album_url(body.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "URL must be an open.spotify.com public playlist or album link"
            ),
        )
    service = ImportService(session)
    job = await service.scan_external_playlist(
        user_id=current_user.id,
        source="spotify",
        url=body.url.strip(),
    )
    return ImportJobResponse.model_validate(job)


@router.post(
    "/{job_id}/start",
    response_model=ImportJobResponse,
)
@limiter.limit("5/minute")
async def start_import(
    request: Request,
    job_id: int,
    body: ImportStartRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.start_import(
        job_id, current_user.id, body.track_indices
    )
    return ImportJobResponse.model_validate(job)


@router.get(
    "/{job_id}/status",
    response_model=ImportJobResponse,
)
@limiter.limit("60/minute")
async def get_import_status(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.get_job_status(job_id, current_user.id)
    response = ImportJobResponse.model_validate(job)
    if job.status == "queued":
        response.queue_position = await service.get_queue_position(
            job_id, current_user.id
        )
    return response


@router.get(
    "/active",
    response_model=ImportJobResponse | None,
)
@limiter.limit("30/minute")
async def get_active_import(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse | None:
    service = ImportService(session)
    job = await service.get_active_job(current_user.id)
    if not job:
        return None
    response = ImportJobResponse.model_validate(job)
    if job.status == "queued":
        response.queue_position = await service.get_queue_position(
            job.id, current_user.id
        )
    return response


@router.post(
    "/{job_id}/cancel",
    response_model=ImportJobResponse,
)
@limiter.limit("10/minute")
async def cancel_import(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    service = ImportService(session)
    job = await service.cancel_job(job_id, current_user.id)
    return ImportJobResponse.model_validate(job)


async def _scan_account(
    provider: str,
    body: AccountImportRequest,
    session: AsyncSession,
    current_user: User,
) -> ImportJobResponse:
    """Shared handler for all account-based import endpoints."""
    if body.source not in ("liked", "playlist"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='source must be "liked" or "playlist"',
        )
    if body.source == "playlist" and not body.playlist_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="playlist_id is required when source is \"playlist\"",
        )

    linked_svc = LinkedAccountService(session)
    account = await linked_svc.get_account(current_user.id, provider)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider.capitalize()} account is not connected. "
                "Connect it in account settings first."
            ),
        )
    account = await linked_svc.refresh_if_expired(account)

    resolved_source = (
        body.playlist_id if body.source == "playlist" else "liked"
    )
    import_svc = ImportService(session)
    job = await import_svc.scan_account_library(
        user_id=current_user.id,
        provider=provider,
        source=resolved_source,
        account=account,
    )
    return ImportJobResponse.model_validate(job)


@router.post(
    "/spotify_account",
    response_model=ImportJobResponse,
    summary="Import from connected Spotify account",
)
@limiter.limit("5/minute")
async def scan_spotify_account(
    request: Request,
    body: AccountImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    return await _scan_account("spotify", body, session, current_user)


@router.post(
    "/soundcloud_account",
    response_model=ImportJobResponse,
    summary="Import liked tracks from connected SoundCloud account",
)
@limiter.limit("5/minute")
async def scan_soundcloud_account(
    request: Request,
    body: AccountImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    return await _scan_account("soundcloud", body, session, current_user)


@router.post(
    "/vk_account",
    response_model=ImportJobResponse,
    summary="Import audio from connected VK account",
)
@limiter.limit("5/minute")
async def scan_vk_account(
    request: Request,
    body: AccountImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    return await _scan_account("vk", body, session, current_user)
