"""Album CRUD endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.user import User
from app.schemas.album import (
    AlbumCreateRequest,
    AlbumResponse,
    AlbumTrackOrderRequest,
    AlbumUpdateRequest,
    AlbumWithTracksResponse,
)
from app.services.album_service import AlbumService
from app.services.track_playback_health_service import (
    is_track_playback_suppressed,
)
from app.services.track_response_build import dedupe_and_build_track_list
from app.utils.pagination_cursor import decode_cursor, encode_cursor

router = APIRouter(prefix="/albums", tags=["albums"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _track_cursor_data(cursor: str) -> tuple[int, int] | None:
    data = decode_cursor(cursor)
    if data is None:
        return None
    raw_position = data.get("position")
    raw_track_id = data.get("track_id")
    if not isinstance(raw_position, int) or not isinstance(raw_track_id, int):
        return None
    return raw_position, raw_track_id


def _track_next_cursor(
    rows: list[tuple[object, int, int]],
) -> str | None:
    if not rows:
        return None
    _, position, track_id = rows[-1]
    return encode_cursor(
        {"position": position, "track_id": track_id}
    )


@router.post(
    "",
    response_model=AlbumResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new album",
)
@limiter.limit("30/minute")
async def create_album(
    request: Request,
    body: AlbumCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumResponse:
    service = AlbumService(session)
    album = await service.create(
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        is_public=body.is_public,
    )
    return AlbumResponse.model_validate(album)


@router.get(
    "/{album_id}",
    response_model=AlbumWithTracksResponse,
    summary="Get album with its tracks",
)
@limiter.limit("200/minute")
async def get_album(
    request: Request,
    album_id: int,
    tracks_page: int | None = Query(None, ge=1),
    tracks_size: int = Query(50, ge=1, le=100),
    tracks_cursor: str | None = Query(None, max_length=512),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> AlbumWithTracksResponse:
    service = AlbumService(session)
    album = await service.get_with_tracks(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )
    is_owner = (
        current_user
        and current_user.id == album.owner_id
    )
    is_admin = bool(current_user and current_user.is_admin)
    if not album.is_public and not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )
    tracks_next_cursor = None
    if tracks_cursor is not None:
        parsed = _track_cursor_data(tracks_cursor)
        if parsed is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor",
            )
        cursor_position, cursor_track_id = parsed
        track_rows, tracks_total, tracks_has_more = (
            await service.list_tracks_cursor(
                album_id=album_id,
                cursor_position=cursor_position,
                cursor_track_id=cursor_track_id,
                size=tracks_size,
                include_suppressed=bool(is_owner or is_admin),
            )
        )
        raw_tracks = [row[0] for row in track_rows]
        page = tracks_page or 1
        size = tracks_size
        tracks_next_cursor = (
            _track_next_cursor(track_rows) if tracks_has_more else None
        )
    elif tracks_page is None:
        raw_tracks = list(album.tracks)
        if not is_owner and not is_admin:
            raw_tracks = [
                t
                for t in raw_tracks
                if not is_track_playback_suppressed(t)
            ]
        tracks_total = len(raw_tracks)
        page = 1
        size = len(raw_tracks)
        tracks_has_more = False
    elif tracks_page == 1:
        track_rows, tracks_total, tracks_has_more = (
            await service.list_tracks_cursor(
                album_id=album_id,
                cursor_position=None,
                cursor_track_id=None,
                size=tracks_size,
                include_suppressed=bool(is_owner or is_admin),
            )
        )
        raw_tracks = [row[0] for row in track_rows]
        page = tracks_page
        size = tracks_size
        tracks_next_cursor = (
            _track_next_cursor(track_rows) if tracks_has_more else None
        )
    else:
        raw_tracks, tracks_total = await service.list_tracks_page(
            album_id=album_id,
            page=tracks_page,
            size=tracks_size,
            include_suppressed=bool(is_owner or is_admin),
        )
        page = tracks_page
        size = tracks_size
        tracks_has_more = (page * size) < tracks_total
    tracks = await dedupe_and_build_track_list(session, raw_tracks)
    return AlbumWithTracksResponse(
        **AlbumResponse.model_validate(album).model_dump(),
        tracks=tracks,
        tracks_total=tracks_total,
        tracks_page=page,
        tracks_size=size,
        tracks_has_more=tracks_has_more,
        tracks_next_cursor=tracks_next_cursor,
    )


@router.patch(
    "/{album_id}",
    response_model=AlbumResponse,
    summary="Update album metadata (owner only)",
)
@limiter.limit("30/minute")
async def update_album(
    request: Request,
    album_id: int,
    body: AlbumUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumResponse:
    service = AlbumService(session)
    album = await service.update(
        album_id=album_id,
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        is_public=body.is_public,
        allow_admin=current_user.is_admin,
    )
    return AlbumResponse.model_validate(album)


@router.delete(
    "/{album_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an album (owner only)",
)
@limiter.limit("30/minute")
async def delete_album(
    request: Request,
    album_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = AlbumService(session)
    await service.delete(
        album_id=album_id,
        user_id=current_user.id,
        allow_admin=current_user.is_admin,
    )


@router.post(
    "/{album_id}/tracks/{track_id}",
    status_code=status.HTTP_200_OK,
    summary="Add a track to an album (owner only, track must be yours)",
)
@limiter.limit("30/minute")
async def add_track_to_album(
    request: Request,
    album_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = AlbumService(session)
    await service.add_track(
        album_id=album_id,
        track_id=track_id,
        user_id=current_user.id,
        allow_admin=current_user.is_admin,
    )
    return {"album_id": album_id, "track_id": track_id}


@router.delete(
    "/{album_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a track from an album (owner only)",
)
@limiter.limit("30/minute")
async def remove_track_from_album(
    request: Request,
    album_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = AlbumService(session)
    await service.remove_track(
        album_id=album_id,
        track_id=track_id,
        user_id=current_user.id,
        allow_admin=current_user.is_admin,
    )


@router.put(
    "/{album_id}/track-order",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set album track order (owner or admin)",
)
@limiter.limit("30/minute")
async def set_album_track_order(
    request: Request,
    album_id: int,
    body: AlbumTrackOrderRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = AlbumService(session)
    await service.reorder_tracks(
        album_id=album_id,
        track_ids=body.track_ids,
        user_id=current_user.id,
        allow_admin=current_user.is_admin,
    )
