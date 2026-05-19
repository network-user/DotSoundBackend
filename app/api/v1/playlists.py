from datetime import datetime

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db, get_optional_user
from app.models.user import User
from app.schemas.playlist import (
    PlaylistAddTrack,
    PlaylistCreate,
    PlaylistListResponse,
    PlaylistResponse,
    PlaylistTrackOrderRequest,
    PlaylistUpdate,
    PlaylistWithTracksResponse,
)
from app.schemas.playlist_collab import (
    PlaylistCollaboratorItem,
    PlaylistInviteAccept,
    PlaylistInviteOut,
)
from app.services.playlist_collab_service import (
    PlaylistCollabService,
)
from app.services.playlist_service import _UNSET, PlaylistService
from app.services.track_response_build import dedupe_and_build_track_list
from app.utils.pagination_cursor import decode_cursor, encode_cursor

router = APIRouter(prefix="/playlists", tags=["playlists"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_COVER_BYTES = 5 * 1024 * 1024
_ALLOWED_PLAYLIST_COVER_CT = frozenset(
    {"image/jpeg", "image/png", "image/webp"},
)


def _playlist_cursor_data(cursor: str) -> tuple[datetime, int] | None:
    data = decode_cursor(cursor)
    if data is None:
        return None
    raw_created_at = data.get("created_at")
    raw_id = data.get("id")
    if not isinstance(raw_created_at, str) or not isinstance(raw_id, int):
        return None
    try:
        return datetime.fromisoformat(raw_created_at), raw_id
    except ValueError:
        return None


def _playlist_next_cursor(items: list[PlaylistResponse]) -> str | None:
    if not items:
        return None
    last = items[-1]
    return encode_cursor(
        {"created_at": last.created_at.isoformat(), "id": last.id}
    )


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


@router.get(
    "/featured",
    response_model=list[PlaylistWithTracksResponse],
    summary="Get featured/editorial playlists",
)
@limiter.limit("120/minute")
async def get_featured_playlists(
    request: Request,
    limit: int = Query(10, ge=1, le=30),
    session: AsyncSession = Depends(get_db),
) -> list[PlaylistWithTracksResponse]:
    service = PlaylistService(session)
    pairs = await service.list_featured_with_tracks(limit=limit)
    results = []
    for p, tracks in pairs:
        resp = PlaylistWithTracksResponse.model_validate(p)
        resp.tracks = await dedupe_and_build_track_list(session, tracks)
        results.append(resp)
    return results


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
        description=data.description,
    )
    logger.info("playlist_created_endpoint", playlist_id=playlist.id)
    return PlaylistResponse.model_validate(playlist)


@router.get(
    "",
    response_model=PlaylistListResponse,
    summary="List playlists owned by the authenticated user",
)
@limiter.limit("120/minute")
async def list_playlists(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistListResponse:
    structlog.contextvars.bind_contextvars(owner_id=current_user.id)
    service = PlaylistService(session)
    if cursor is None:
        rows, total = await service.list_by_owner(
            owner_id=current_user.id, page=page, size=size
        )
        has_more = page * size < total
    else:
        parsed = _playlist_cursor_data(cursor)
        if parsed is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor",
            )
        cursor_created_at, cursor_id = parsed
        rows, total, has_more = await service.list_by_owner_cursor(
            owner_id=current_user.id,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            size=size,
        )
    items = []
    for playlist, count in rows:
        r = PlaylistResponse.model_validate(playlist)
        r.track_count = count
        items.append(r)
    return PlaylistListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=has_more,
        next_cursor=_playlist_next_cursor(items) if has_more else None,
    )


@router.get(
    "/search",
    response_model=PlaylistListResponse,
    summary="Search public playlists by name",
)
@limiter.limit("60/minute")
async def search_playlists(
    request: Request,
    q: str = Query("", max_length=256),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> PlaylistListResponse:
    if not q.strip():
        return PlaylistListResponse(
            items=[],
            total=0,
            page=page,
            size=size,
        )
    service = PlaylistService(session)
    if cursor is None:
        playlists, total = await service.search_public(
            query=q.strip(),
            page=page,
            size=size,
            exclude_owner_id=current_user.id if current_user else None,
        )
        has_more = page * size < total
    else:
        parsed = _playlist_cursor_data(cursor)
        if parsed is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor",
            )
        cursor_created_at, cursor_id = parsed
        playlists, total, has_more = await service.search_public_cursor(
            query=q.strip(),
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            size=size,
            exclude_owner_id=current_user.id if current_user else None,
        )
    items = [PlaylistResponse.model_validate(p) for p in playlists]
    return PlaylistListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=has_more,
        next_cursor=_playlist_next_cursor(items) if has_more else None,
    )


@router.get(
    "/{playlist_id}",
    response_model=PlaylistWithTracksResponse,
    summary="Get a playlist with its tracks",
)
@limiter.limit("200/minute")
async def get_playlist(
    request: Request,
    playlist_id: int,
    tracks_page: int | None = Query(None, ge=1),
    tracks_size: int = Query(50, ge=1, le=100),
    tracks_cursor: str | None = Query(None, max_length=512),
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
    is_owner = current_user and current_user.id == playlist.owner_id
    is_admin = bool(current_user and current_user.is_admin)
    if not playlist.is_public and not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
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
                playlist_id,
                cursor_position=cursor_position,
                cursor_track_id=cursor_track_id,
                size=tracks_size,
            )
        )
        tracks = [row[0] for row in track_rows]
        page = tracks_page or 1
        size = tracks_size
        tracks_next_cursor = (
            _track_next_cursor(track_rows) if tracks_has_more else None
        )
    elif tracks_page is None:
        tracks = await service.get_tracks(playlist_id)
        tracks_total = len(tracks)
        page = 1
        size = len(tracks)
        tracks_has_more = False
    elif tracks_page == 1:
        track_rows, tracks_total, tracks_has_more = (
            await service.list_tracks_cursor(
                playlist_id,
                cursor_position=None,
                cursor_track_id=None,
                size=tracks_size,
            )
        )
        tracks = [row[0] for row in track_rows]
        page = tracks_page
        size = tracks_size
        tracks_next_cursor = (
            _track_next_cursor(track_rows) if tracks_has_more else None
        )
    else:
        tracks, tracks_total = await service.list_tracks_page(
            playlist_id,
            page=tracks_page,
            size=tracks_size,
        )
        page = tracks_page
        size = tracks_size
        tracks_has_more = (page * size) < tracks_total
    result = PlaylistWithTracksResponse.model_validate(playlist)
    result.tracks = await dedupe_and_build_track_list(session, tracks)
    result.tracks_total = tracks_total
    result.tracks_page = page
    result.tracks_size = size
    result.tracks_has_more = tracks_has_more
    result.tracks_next_cursor = tracks_next_cursor
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
    desc: object = (
        data.description
        if "description" in data.model_fields_set
        else _UNSET
    )
    playlist = await service.update(
        playlist_id=playlist_id,
        requester_id=current_user.id,
        name=data.name,
        is_public=data.is_public,
        description=desc,
        allow_admin=current_user.is_admin,
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
    await service.delete(
        playlist_id,
        current_user.id,
        allow_admin=current_user.is_admin,
    )
    logger.info("playlist_deleted_endpoint", playlist_id=playlist_id)


@router.post(
    "/{playlist_id}/cover",
    response_model=PlaylistResponse,
    summary="Upload or replace playlist cover (owner only)",
)
@limiter.limit("30/minute")
async def upload_playlist_cover(
    request: Request,
    playlist_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistResponse:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id,
        requester_id=current_user.id,
    )
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_PLAYLIST_COVER_CT:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Cover must be JPEG, PNG, or WebP",
        )
    data = await file.read()
    if len(data) > _MAX_COVER_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Cover exceeds 5 MB limit",
        )
    service = PlaylistService(session)
    playlist = await service.upload_owner_cover(
        playlist_id,
        requester_id=current_user.id,
        data=data,
        content_type=mime,
    )
    logger.info(
        "playlist_cover_uploaded",
        playlist_id=playlist_id,
    )
    return PlaylistResponse.model_validate(playlist)


@router.delete(
    "/{playlist_id}/cover",
    response_model=PlaylistResponse,
    summary="Remove playlist cover and opt out of auto collage",
)
@limiter.limit("30/minute")
async def delete_playlist_cover(
    request: Request,
    playlist_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistResponse:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id,
        requester_id=current_user.id,
    )
    service = PlaylistService(session)
    playlist = await service.delete_owner_cover(
        playlist_id,
        current_user.id,
    )
    logger.info(
        "playlist_cover_removed",
        playlist_id=playlist_id,
    )
    return PlaylistResponse.model_validate(playlist)


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
        allow_admin=current_user.is_admin,
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
    await service.remove_track(
        playlist_id,
        track_id,
        current_user.id,
        allow_admin=current_user.is_admin,
    )


@router.put(
    "/{playlist_id}/track-order",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set playlist track order (owner/editor/admin)",
)
@limiter.limit("60/minute")
async def set_playlist_track_order(
    request: Request,
    playlist_id: int,
    body: PlaylistTrackOrderRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = PlaylistService(session)
    await service.reorder_tracks(
        playlist_id=playlist_id,
        ordered_track_ids=body.track_ids,
        requester_id=current_user.id,
        allow_admin=current_user.is_admin,
    )


@router.get(
    "/{playlist_id}/collaborators",
    response_model=list[PlaylistCollaboratorItem],
    summary="List collaborators of a playlist (owner/admin only)",
)
@limiter.limit("60/minute")
async def list_playlist_collaborators(
    request: Request,
    playlist_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlaylistCollaboratorItem]:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id, requester_id=current_user.id
    )
    service = PlaylistService(session)
    rows = await service.get_collaborators(
        playlist_id=playlist_id,
        requester_id=current_user.id,
        allow_admin=current_user.is_admin,
    )
    return [PlaylistCollaboratorItem(**r) for r in rows]


@router.delete(
    "/{playlist_id}/collaborators/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a collaborator from a playlist (owner/admin only)",
)
@limiter.limit("30/minute")
async def remove_playlist_collaborator(
    request: Request,
    playlist_id: int,
    target_user_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(
        playlist_id=playlist_id,
        target_user_id=target_user_id,
        requester_id=current_user.id,
    )
    service = PlaylistService(session)
    await service.remove_collaborator(
        playlist_id=playlist_id,
        target_user_id=target_user_id,
        requester_id=current_user.id,
        allow_admin=current_user.is_admin,
    )


@router.post(
    "/{playlist_id}/invites",
    response_model=PlaylistInviteOut,
    summary="Create one-time collaboration invite (owner only)",
)
@limiter.limit("20/minute")
async def create_playlist_invite(
    request: Request,
    playlist_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistInviteOut:
    svc = PlaylistCollabService(session)
    raw, exp = await svc.create_invite(playlist_id, current_user)
    return PlaylistInviteOut(
        token=raw,
        expires_at=exp,
    )


@router.post(
    "/invites/accept",
    response_model=PlaylistResponse,
    summary="Accept a playlist invite (authenticated)",
)
@limiter.limit("30/minute")
async def accept_playlist_invite(
    request: Request,
    body: PlaylistInviteAccept,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistResponse:
    csvc = PlaylistCollabService(session)
    pid = await csvc.accept(body.token, current_user)
    psvc = PlaylistService(session)
    p = await psvc.get(pid)
    if not p:
        raise HTTPException(404, "not_found")
    return PlaylistResponse.model_validate(p)
