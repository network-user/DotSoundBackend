"""Admin HTTP API for artist catalog editing and sync triggers."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.schemas import (
    ArtistSupplementalBatchImportRequest,
    ArtistSupplementalBatchImportResponse,
    ArtistSupplementalBatchPromptRequest,
    ArtistSupplementalBatchPromptResponse,
    AdminTrackListResponse,
    AdminTrackResponse,
)
from app.core.rate_limit import limiter
from app.dependencies import (
    get_db,
    require_admin_session,
    require_step_up,
)
from app.models.user import User
from app.schemas.admin_artist_catalog import (
    AdminArtistCatalogOverviewResponse,
    AdminArtistSoundcloudPatch,
    AdminCatalogReleaseCreate,
    AdminCatalogReleaseOrderBody,
    AdminCatalogReleasePatch,
    AdminCatalogReleaseSummaryResponse,
    AdminCatalogReleaseSyncQueuedResponse,
    AdminCatalogReleaseTracksBody,
    AdminCatalogSyncQueuedResponse,
)
from app.schemas.artist_catalog import ArtistCatalogReleaseDetailResponse
from app.services.admin_artist_catalog_service import (
    AdminArtistCatalogService,
)
from app.services.admin_artist_supplemental_service import (
    AdminArtistSupplementalService,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/artists", tags=["admin-artist-catalog"])


@router.post(
    "/supplemental/batch-prompt",
    response_model=ArtistSupplementalBatchPromptResponse,
)
@limiter.limit("20/minute")
async def admin_artist_supplemental_batch_prompt(
    request: Request,
    body: ArtistSupplementalBatchPromptRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> ArtistSupplementalBatchPromptResponse:
    svc = AdminArtistSupplementalService(session)
    prompt, count = await svc.batch_prompt(body.artist_ids)
    return ArtistSupplementalBatchPromptResponse(
        prompt=prompt,
        artist_count=count,
    )


@router.post(
    "/supplemental/batch-import",
    response_model=ArtistSupplementalBatchImportResponse,
)
@limiter.limit("10/minute")
async def admin_artist_supplemental_batch_import(
    request: Request,
    body: ArtistSupplementalBatchImportRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> ArtistSupplementalBatchImportResponse:
    svc = AdminArtistSupplementalService(session)
    imported, errors = await svc.batch_import(body.raw_response)
    await session.commit()
    return ArtistSupplementalBatchImportResponse(
        imported=imported,
        errors=errors,
    )


@router.get(
    "/{artist_id}/catalog/overview",
    response_model=AdminArtistCatalogOverviewResponse,
)
@limiter.limit("120/minute")
async def admin_catalog_overview(
    request: Request,
    artist_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminArtistCatalogOverviewResponse:
    svc = AdminArtistCatalogService(session)
    out = await svc.overview(artist_id)
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    return out


_MAX_ARTIST_AVATAR_BYTES = 2 * 1024 * 1024
_ALLOWED_ARTIST_AVATAR_CT = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


@router.post(
    "/{artist_id}/catalog/avatar",
    response_model=AdminArtistCatalogOverviewResponse,
)
@limiter.limit("20/minute")
async def admin_catalog_upload_artist_avatar(
    request: Request,
    artist_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminArtistCatalogOverviewResponse:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_ARTIST_AVATAR_CT:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar must be JPEG, PNG, or WebP",
        )
    data = await file.read()
    if len(data) > _MAX_ARTIST_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar exceeds 2 MB limit",
        )
    svc = AdminArtistCatalogService(session)
    out = await svc.upload_artist_avatar(
        artist_id,
        data=data,
        admin_user_id=admin.id,
    )
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    return out


@router.patch(
    "/{artist_id}/catalog/soundcloud",
    response_model=AdminArtistCatalogOverviewResponse,
)
@limiter.limit("30/minute")
async def admin_catalog_patch_soundcloud(
    request: Request,
    artist_id: int,
    body: AdminArtistSoundcloudPatch,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminArtistCatalogOverviewResponse:
    svc = AdminArtistCatalogService(session)
    try:
        out = await svc.patch_soundcloud(artist_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    return out


@router.get(
    "/{artist_id}/catalog/releases/{release_id}",
    response_model=ArtistCatalogReleaseDetailResponse,
)
@limiter.limit("120/minute")
async def admin_catalog_release_detail(
    request: Request,
    artist_id: int,
    release_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> ArtistCatalogReleaseDetailResponse:
    svc = AdminArtistCatalogService(session)
    out = await svc.release_detail(artist_id, release_id)
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist or catalog release not found",
        )
    return out


@router.post(
    "/{artist_id}/catalog/releases",
    response_model=AdminCatalogReleaseSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def admin_catalog_create_release(
    request: Request,
    artist_id: int,
    body: AdminCatalogReleaseCreate,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminCatalogReleaseSummaryResponse:
    svc = AdminArtistCatalogService(session)
    try:
        out = await svc.create_release(artist_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    return out


@router.patch(
    "/{artist_id}/catalog/releases/{release_id}",
    response_model=AdminCatalogReleaseSummaryResponse,
)
@limiter.limit("60/minute")
async def admin_catalog_patch_release(
    request: Request,
    artist_id: int,
    release_id: int,
    body: AdminCatalogReleasePatch,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminCatalogReleaseSummaryResponse:
    svc = AdminArtistCatalogService(session)
    out = await svc.patch_release(artist_id, release_id, body)
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist or catalog release not found",
        )
    return out


@router.delete(
    "/{artist_id}/catalog/releases/{release_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("60/minute")
async def admin_catalog_delete_release(
    request: Request,
    artist_id: int,
    release_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> Response:
    svc = AdminArtistCatalogService(session)
    ok = await svc.delete_release(artist_id, release_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist or catalog release not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{artist_id}/catalog/release-display-order",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("60/minute")
async def admin_catalog_reorder_releases(
    request: Request,
    artist_id: int,
    body: AdminCatalogReleaseOrderBody,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> Response:
    svc = AdminArtistCatalogService(session)
    try:
        await svc.reorder_releases(
            artist_id,
            body.ordered_release_ids,
        )
    except ValueError as exc:
        msg = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if msg == "artist not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=msg) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{artist_id}/catalog/releases/{release_id}/tracks",
    response_model=ArtistCatalogReleaseDetailResponse,
)
@limiter.limit("60/minute")
async def admin_catalog_set_release_tracks(
    request: Request,
    artist_id: int,
    release_id: int,
    body: AdminCatalogReleaseTracksBody,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> ArtistCatalogReleaseDetailResponse:
    svc = AdminArtistCatalogService(session)
    try:
        out = await svc.set_release_tracks(
            artist_id,
            release_id,
            body.track_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist or catalog release not found",
        )
    return out


@router.get(
    "/{artist_id}/catalog/tracks/search",
    response_model=AdminTrackListResponse,
)
@limiter.limit("120/minute")
async def admin_catalog_search_tracks_for_artist(
    request: Request,
    artist_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    catalog_svc = AdminArtistCatalogService(session)
    if not await catalog_svc.artist_exists(artist_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    svc = AdminService(session)
    tracks, total = await svc.list_tracks_for_artist(
        artist_id,
        page=page,
        size=size,
        search=search,
    )
    return AdminTrackListResponse(
        items=[AdminTrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/{artist_id}/catalog/sync",
    response_model=AdminCatalogSyncQueuedResponse,
)
@limiter.limit("10/minute")
async def admin_catalog_enqueue_full_sync(
    request: Request,
    artist_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_step_up("catalog.sync.run")),
) -> AdminCatalogSyncQueuedResponse:
    svc = AdminArtistCatalogService(session)
    try:
        await svc.enqueue_full_sync(artist_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "artist not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        if msg == AdminArtistCatalogService.COOLDOWN_ENQUEUE_DETAIL:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc
    return AdminCatalogSyncQueuedResponse(
        queued=True,
        task="sync_artist_catalog_task",
    )


@router.post(
    "/{artist_id}/catalog/releases/{release_id}/sync",
    response_model=AdminCatalogReleaseSyncQueuedResponse,
)
@limiter.limit("20/minute")
async def admin_catalog_enqueue_release_sync(
    request: Request,
    artist_id: int,
    release_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_step_up("catalog.sync.run")),
) -> AdminCatalogReleaseSyncQueuedResponse:
    svc = AdminArtistCatalogService(session)
    try:
        sc_id = await svc.enqueue_release_sync(artist_id, release_id)
    except ValueError as exc:
        msg = str(exc)
        if msg in (
            "artist not found",
            "release not found",
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        if msg == AdminArtistCatalogService.COOLDOWN_ENQUEUE_DETAIL:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc
    return AdminCatalogReleaseSyncQueuedResponse(
        queued=True,
        task="sync_artist_catalog_release_task",
        soundcloud_album_id=sc_id,
    )
