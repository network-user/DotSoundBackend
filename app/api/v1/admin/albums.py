"""Admin endpoints for user album editing."""

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

from app.api.v1.admin.schemas import (
    AdminAlbumDetailResponse,
    AdminAlbumListItem,
    AdminAlbumListResponse,
    AdminAlbumPatchRequest,
    AdminAlbumReorderRequest,
    AdminTrackResponse,
)
from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin_session
from app.models.user import User
from app.schemas.album import AlbumResponse
from app.services.admin_album_service import AdminAlbumService
from app.services.track_response_build import dedupe_and_build_track_list

router = APIRouter(prefix="/albums", tags=["admin-albums"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_COVER_BYTES = 5 * 1024 * 1024
_ALLOWED_COVER_CT = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


@router.get(
    "",
    response_model=AdminAlbumListResponse,
    summary="[Admin] List albums",
)
@limiter.limit("60/minute")
async def admin_list_albums(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminAlbumListResponse:
    svc = AdminAlbumService(session)
    rows, total = await svc.list_albums(
        page=page,
        size=size,
        search=search,
    )
    items = [
        AdminAlbumListItem(
            id=album.id,
            title=album.title,
            owner_id=album.owner_id,
            is_public=album.is_public,
            created_at=album.created_at,
            track_count=tc,
        )
        for album, tc in rows
    ]
    return AdminAlbumListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{album_id}",
    response_model=AdminAlbumDetailResponse,
    summary="[Admin] Get album with tracks",
)
@limiter.limit("120/minute")
async def admin_get_album(
    request: Request,
    album_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminAlbumDetailResponse:
    svc = AdminAlbumService(session)
    album = await svc.get_detail(album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )
    built = await dedupe_and_build_track_list(
        session,
        list(album.tracks),
    )
    tracks = [
        AdminTrackResponse.model_validate(
            br.model_dump(),
        )
        for br in built
    ]
    base = AlbumResponse.model_validate(album)
    return AdminAlbumDetailResponse(
        **base.model_dump(),
        tracks=tracks,
    )


@router.patch(
    "/{album_id}",
    response_model=AlbumResponse,
    summary="[Admin] Update album metadata",
)
@limiter.limit("60/minute")
async def admin_patch_album(
    request: Request,
    album_id: int,
    body: AdminAlbumPatchRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AlbumResponse:
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    svc = AdminAlbumService(session)
    album = await svc.update_metadata(
        album_id,
        title=fields.get("title"),
        description=fields.get("description"),
        is_public=fields.get("is_public"),
        owner_id=fields.get("owner_id"),
    )
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )
    return AlbumResponse.model_validate(album)


@router.post(
    "/{album_id}/cover",
    response_model=AlbumResponse,
    summary="[Admin] Upload album cover image",
)
@limiter.limit("30/minute")
async def admin_upload_album_cover(
    request: Request,
    album_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AlbumResponse:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_COVER_CT:
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
    svc = AdminAlbumService(session)
    album = await svc.upload_cover(
        album_id,
        data=data,
        content_type=mime,
    )
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found",
        )
    logger.info("admin_album_cover_uploaded", album_id=album_id)
    return AlbumResponse.model_validate(album)


@router.post(
    "/{album_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Add any active track to album",
)
@limiter.limit("60/minute")
async def admin_add_album_track(
    request: Request,
    album_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> None:
    svc = AdminAlbumService(session)
    await svc.add_track(album_id, track_id)


@router.delete(
    "/{album_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Remove track from album",
)
@limiter.limit("60/minute")
async def admin_remove_album_track(
    request: Request,
    album_id: int,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> None:
    svc = AdminAlbumService(session)
    await svc.remove_track(album_id, track_id)


@router.put(
    "/{album_id}/track-order",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Set album track order",
)
@limiter.limit("60/minute")
async def admin_reorder_album_tracks(
    request: Request,
    album_id: int,
    body: AdminAlbumReorderRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> None:
    svc = AdminAlbumService(session)
    await svc.reorder_tracks(album_id, body.track_ids)
