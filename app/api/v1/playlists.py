import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.user import User
from app.schemas.playlist import (
    PlaylistAddTrack,
    PlaylistCreate,
    PlaylistResponse,
    PlaylistUpdate,
    PlaylistWithTracksResponse,
)
from app.schemas.track import TrackResponse
from app.services.playlist_service import PlaylistService

router = APIRouter(prefix="/playlists", tags=["playlists"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "",
    response_model=PlaylistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new playlist",
)
@limiter.limit("30/minute")
async def create_playlist(
    request: Request,
    data: PlaylistCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistResponse:
    structlog.contextvars.bind_contextvars(owner_id=current_user.id)
    service = PlaylistService(session)
    playlist = await service.create(
        name=data.name,
        owner_id=current_user.id,
        is_public=data.is_public,
    )
    logger.info(
        "playlist_created_endpoint", playlist_id=playlist.id
    )
    return PlaylistResponse.model_validate(playlist)


@router.get(
    "",
    response_model=list[PlaylistResponse],
    summary="List playlists owned by the authenticated user",
)
@limiter.limit("120/minute")
async def list_playlists(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlaylistResponse]:
    structlog.contextvars.bind_contextvars(owner_id=current_user.id)
    service = PlaylistService(session)
    playlists, _ = await service.list_by_owner(
        owner_id=current_user.id, page=page, size=size
    )
    return [PlaylistResponse.model_validate(p) for p in playlists]


@router.get(
    "/{playlist_id}",
    response_model=PlaylistWithTracksResponse,
    summary="Get a playlist with its tracks",
)
@limiter.limit("200/minute")
async def get_playlist(
    request: Request,
    playlist_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> PlaylistWithTracksResponse:
    structlog.contextvars.bind_contextvars(playlist_id=playlist_id)
    service = PlaylistService(session)
    playlist = await service.get(playlist_id)
    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )
    is_owner = (
        current_user
        and current_user.id == playlist.owner_id
    )
    if not playlist.is_public and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )
    tracks = await service.get_tracks(playlist_id)
    result = PlaylistWithTracksResponse.model_validate(playlist)
    result.tracks = [TrackResponse.model_validate(t) for t in tracks]
    return result


@router.put(
    "/{playlist_id}",
    response_model=PlaylistResponse,
    summary="Update playlist name or visibility",
)
@limiter.limit("30/minute")
async def update_playlist(
    request: Request,
    playlist_id: int,
    data: PlaylistUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistResponse:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id, requester_id=current_user.id
    )
    service = PlaylistService(session)
    playlist = await service.update(
        playlist_id=playlist_id,
        requester_id=current_user.id,
        name=data.name,
        is_public=data.is_public,
    )
    return PlaylistResponse.model_validate(playlist)


@router.delete(
    "/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a playlist",
)
@limiter.limit("30/minute")
async def delete_playlist(
    request: Request,
    playlist_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id, requester_id=current_user.id
    )
    service = PlaylistService(session)
    await service.delete(playlist_id, current_user.id)
    logger.info(
        "playlist_deleted_endpoint", playlist_id=playlist_id
    )


@router.post(
    "/{playlist_id}/tracks",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add a track to a playlist",
)
@limiter.limit("60/minute")
async def add_track(
    request: Request,
    playlist_id: int,
    data: PlaylistAddTrack,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id,
        track_id=data.track_id,
        requester_id=current_user.id,
    )
    service = PlaylistService(session)
    await service.add_track(
        playlist_id=playlist_id,
        track_id=data.track_id,
        requester_id=current_user.id,
        position=data.position,
    )


@router.delete(
    "/{playlist_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a track from a playlist",
)
@limiter.limit("60/minute")
async def remove_track(
    request: Request,
    playlist_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id,
        track_id=track_id,
        requester_id=current_user.id,
    )
    service = PlaylistService(session)
    await service.remove_track(playlist_id, track_id, current_user.id)
