"""Admin endpoints for user playlist editing."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.schemas import (
    AdminPlaylistCreateEditorialRequest,
    AdminPlaylistDetailResponse,
    AdminPlaylistImportRequest,
    AdminPlaylistListItem,
    AdminPlaylistListResponse,
    AdminPlaylistPatchRequest,
    AdminPlaylistReorderRequest,
    AdminTrackResponse,
)
from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin_session
from app.models.user import User
from app.schemas.playlist import PlaylistResponse
from app.services.admin_playlist_service import AdminPlaylistService
from app.services.soundcloud_service import SoundCloudService
from app.services.track_response_build import dedupe_and_build_track_list

router = APIRouter(prefix="/playlists", tags=["admin-playlists"])


@router.get(
    "",
    response_model=AdminPlaylistListResponse,
    summary="[Admin] List playlists",
)
@limiter.limit("60/minute")
async def admin_list_playlists(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminPlaylistListResponse:
    svc = AdminPlaylistService(session)
    rows, total = await svc.list_playlists(
        page=page,
        size=size,
        search=search,
    )
    items = [
        AdminPlaylistListItem(
            id=pl.id,
            name=pl.name,
            owner_id=pl.owner_id,
            is_public=pl.is_public,
            created_at=pl.created_at,
            track_count=tc,
        )
        for pl, tc in rows
    ]
    return AdminPlaylistListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{playlist_id}",
    response_model=AdminPlaylistDetailResponse,
    summary="[Admin] Get playlist with tracks",
)
@limiter.limit("120/minute")
async def admin_get_playlist(
    request: Request,
    playlist_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminPlaylistDetailResponse:
    svc = AdminPlaylistService(session)
    playlist = await svc.get_detail(playlist_id)
    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )
    raw_tracks = await svc.get_tracks_raw(playlist_id)
    built = await dedupe_and_build_track_list(session, raw_tracks)
    tracks = [
        AdminTrackResponse.model_validate(br.model_dump()) for br in built
    ]
    base = PlaylistResponse.model_validate(playlist)
    return AdminPlaylistDetailResponse(
        **base.model_dump(),
        tracks=tracks,
    )


@router.post(
    "/import",
    response_model=PlaylistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Import playlist from SoundCloud URL",
)
@limiter.limit("10/minute")
async def admin_import_playlist(
    request: Request,
    body: AdminPlaylistImportRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> PlaylistResponse:
    svc = AdminPlaylistService(session)
    sc_svc = SoundCloudService()
    playlist = await svc.import_from_sc_url(
        sc_service=sc_svc,
        source_url=body.source_url,
        name=body.name,
        owner_id=admin.id,
        make_featured=body.make_featured,
        make_public=body.make_public,
    )
    return PlaylistResponse.model_validate(playlist)


@router.post(
    "/editorial",
    response_model=PlaylistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create editorial (curated) playlist",
)
@limiter.limit("30/minute")
async def admin_create_editorial_playlist(
    request: Request,
    body: AdminPlaylistCreateEditorialRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> PlaylistResponse:
    svc = AdminPlaylistService(session)
    playlist = await svc.create_editorial(
        name=body.name,
        owner_id=admin.id,
        description=body.description,
        is_featured=body.is_featured,
        is_public=body.is_public,
    )
    return PlaylistResponse.model_validate(playlist)


@router.patch(
    "/{playlist_id}",
    response_model=PlaylistResponse,
    summary="[Admin] Update playlist metadata",
)
@limiter.limit("60/minute")
async def admin_patch_playlist(
    request: Request,
    playlist_id: int,
    body: AdminPlaylistPatchRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> PlaylistResponse:
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    svc = AdminPlaylistService(session)
    playlist = await svc.update_metadata(
        playlist_id,
        name=fields.get("name"),
        is_public=fields.get("is_public"),
        owner_id=fields.get("owner_id"),
        is_featured=fields.get("is_featured"),
        description=fields.get("description"),
    )
    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )
    return PlaylistResponse.model_validate(playlist)


@router.post(
    "/{playlist_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Add active track to playlist",
)
@limiter.limit("60/minute")
async def admin_add_playlist_track(
    request: Request,
    playlist_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> None:
    svc = AdminPlaylistService(session)
    await svc.add_track(playlist_id, track_id)


@router.delete(
    "/{playlist_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Remove track from playlist",
)
@limiter.limit("60/minute")
async def admin_remove_playlist_track(
    request: Request,
    playlist_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> None:
    svc = AdminPlaylistService(session)
    await svc.remove_track(playlist_id, track_id)


@router.put(
    "/{playlist_id}/track-order",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Set playlist track order",
)
@limiter.limit("60/minute")
async def admin_reorder_playlist_tracks(
    request: Request,
    playlist_id: int,
    body: AdminPlaylistReorderRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> None:
    svc = AdminPlaylistService(session)
    await svc.reorder_tracks(playlist_id, body.track_ids)
