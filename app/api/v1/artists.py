import uuid
from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import (
    get_current_user,
    get_db,
    require_admin,
)
from app.models.user import User
from app.repositories.artist import ArtistRepository
from app.repositories.artist_follow import (
    ArtistFollowRepository,
)
from app.schemas.artist_follow import (
    ArtistFollowStatusResponse,
    ArtistFollowToggleResponse,
    ArtistListenersResponse,
    FollowedArtistItem,
    FollowedArtistListResponse,
)
from app.services.artist_follow_service import (
    ArtistFollowService,
)
from app.services.artist_stats_service import (
    ArtistStatsService,
)
from app.schemas.artist import (
    ArtistDetailResponse,
    ArtistListResponse,
    ArtistResolveResponse,
    ArtistResponse,
    ArtistSourceProfileResponse,
)
from app.schemas.artist_catalog import (
    ArtistCatalogReleaseDetailResponse,
    ArtistCatalogReleaseListResponse,
)
from app.schemas.artist_supplemental import ArtistSupplementalResponse
from app.api.v1.admin.schemas import (
    ArtistSupplementalBatchImportRequest,
    ArtistSupplementalBatchImportResponse,
    ArtistSupplementalBatchPromptRequest,
    ArtistSupplementalBatchPromptResponse,
)
from app.schemas.track import TrackListResponse
from app.services import artist_enrichment_progress as progress
from app.services.artist_catalog_read_service import (
    ArtistCatalogReadService,
)
from app.services.artist_enrichment_service import (
    ArtistEnrichmentService,
    ArtistNotFound,
)
from app.services.artist_service import ArtistService
from app.services.admin_artist_supplemental_service import (
    AdminArtistSupplementalService,
)
from app.services.track_response_build import dedupe_and_build_track_list


class ArtistEnrichWatchResponse(BaseModel):
    task_id: str


class ArtistEnrichStatusResponse(BaseModel):
    status: str
    stage: str | None = None
    logs: list[str] = []


router = APIRouter(prefix="/artists", tags=["artists"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _compute_age(birth: date | None) -> int | None:
    if birth is None:
        return None
    today = datetime.now(UTC).date()
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years if years >= 0 else None


async def _build_artist_detail(
    session: AsyncSession, artist_id: int
) -> ArtistDetailResponse:
    svc = ArtistService(session)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(
            status_code=404, detail="Artist not found"
        )

    repo = ArtistRepository(session)
    track_ids = await repo.get_artist_track_ids(artist_id)

    image_url: str | None = None
    if artist.image_key:
        image_url = f"/api/v1/tracks/cover_proxy?key={artist.image_key}"

    source_profiles = _build_source_profiles(
        artist.source_profiles
    )

    follow_repo = ArtistFollowRepository(session)
    follower_count = await follow_repo.count_followers(
        artist_id
    )
    stats_svc = ArtistStatsService(session)
    monthly_listeners = (
        await stats_svc.get_current_month_listeners(
            artist_id
        )
    )

    return ArtistDetailResponse(
        id=artist.id,
        name=artist.name,
        image_key=artist.image_key,
        image_url=image_url,
        source=artist.source,
        bio=artist.bio,
        birth_date=artist.birth_date,
        birthplace=artist.birthplace,
        country=artist.country,
        website_url=artist.website_url,
        enrichment_status=artist.enrichment_status,
        enriched_at=artist.enriched_at,
        created_at=artist.created_at,
        track_count=len(track_ids),
        age=_compute_age(artist.birth_date),
        discography=artist.discography,
        source_profiles=source_profiles,
        primary_source_id=artist.primary_source_id,
        follower_count=follower_count,
        monthly_listeners=monthly_listeners,
    )


def _build_source_profiles(
    raw: object,
) -> list[ArtistSourceProfileResponse] | None:
    if not isinstance(raw, list):
        return None
    out: list[ArtistSourceProfileResponse] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(ArtistSourceProfileResponse.model_validate(entry))
        except Exception:
            logger.info(
                "artist_source_profile_skipped",
                payload=entry,
            )
    return out or None


@router.get("", response_model=ArtistListResponse)
async def list_artists(
    q: str | None = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = ArtistService(db)
    if q:
        artists = await svc.search(q, limit)
    else:
        artists = await svc.list_popular(limit)
    return ArtistListResponse(
        items=[ArtistResponse.model_validate(a) for a in artists],
        total=len(artists),
    )


@router.post(
    "/resolve",
    response_model=ArtistResolveResponse,
    summary="Resolve artist name to id, creating a stub if missing.",
)
async def resolve_artist(
    name: str = Query(..., min_length=1, max_length=256),
    db: AsyncSession = Depends(get_db),
) -> ArtistResolveResponse:
    svc = ArtistService(db)
    artist = await svc.find_or_create_by_name(name)
    if artist is None:
        raise HTTPException(status_code=400, detail="Invalid artist name")
    return ArtistResolveResponse(id=artist.id)


@router.get(
    "/{artist_id}/catalog/releases",
    response_model=ArtistCatalogReleaseListResponse,
    summary="List synced catalog releases for an artist.",
)
async def list_artist_catalog_releases(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArtistCatalogReleaseListResponse:
    svc = ArtistCatalogReadService(db)
    out = await svc.list_releases(artist_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return out


@router.get(
    "/{artist_id}/catalog/releases/{release_id}",
    response_model=ArtistCatalogReleaseDetailResponse,
    summary="Catalog release detail with ordered tracks.",
)
async def get_artist_catalog_release(
    artist_id: int,
    release_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArtistCatalogReleaseDetailResponse:
    svc = ArtistCatalogReadService(db)
    out = await svc.get_release_detail(artist_id, release_id)
    if out is None:
        raise HTTPException(
            status_code=404,
            detail="Artist or catalog release not found",
        )
    return out


@router.get(
    "/followed",
    response_model=FollowedArtistListResponse,
    summary="List artists followed by the current user.",
)
@limiter.limit("60/minute")
async def list_followed_artists(
    request: Request,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FollowedArtistListResponse:
    repo = ArtistFollowRepository(db)
    artists = await repo.list_followed_artists(
        current_user.id, limit=limit
    )
    items = [
        FollowedArtistItem(
            id=a.id,
            name=a.name,
            image_key=a.image_key,
            source=a.source,
            bio=a.bio,
        )
        for a in artists
    ]
    return FollowedArtistListResponse(
        items=items, total=len(items)
    )


@router.get(
    "/{artist_id}",
    response_model=ArtistDetailResponse,
)
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
):
    if (settings.sc_client_id or "").strip():
        from app.services.soundcloud_service import SoundCloudService

        svc = ArtistService(db)
        row = await svc.get_by_id(artist_id)
        if (
            row is not None
            and not row.image_key
            and row.soundcloud_user_id is not None
        ):
            sc = SoundCloudService(settings.sc_client_id, db)
            await sc.sync_artist_soundcloud_uploader_profile(
                artist_id,
                None,
                uploader_id=None,
            )
    return await _build_artist_detail(db, artist_id)


@router.post(
    "/{artist_id}/enrich",
    response_model=ArtistDetailResponse,
    summary="[Admin] Manually trigger artist enrichment (sync).",
)
@limiter.limit("10/minute")
async def enrich_artist(
    request: Request,
    artist_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ArtistDetailResponse:
    enrichment = ArtistEnrichmentService(db)
    try:
        await enrichment.enrich(artist_id, bypass_cache=True)
    except ArtistNotFound:
        raise HTTPException(status_code=404, detail="Artist not found")
    return await _build_artist_detail(db, artist_id)


@router.delete(
    "/{artist_id}",
    status_code=204,
    summary="[Admin] Delete an artist (cascade to track_artist links).",
)
@limiter.limit("30/minute")
async def delete_artist(
    request: Request,
    artist_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> None:
    from sqlalchemy import delete, select

    from app.models.artist import Artist, TrackArtist

    existing = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = existing.scalar_one_or_none()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    await db.execute(
        delete(TrackArtist).where(TrackArtist.artist_id == artist_id)
    )
    await db.delete(artist)
    await db.commit()
    logger.info(
        "admin_artist_deleted",
        artist_id=artist_id,
        name=artist.name,
    )


@router.post(
    "/{artist_id}/enrich/watch",
    response_model=ArtistEnrichWatchResponse,
    summary="[Admin] Trigger enrichment in background, return task_id for polling.",
)
@limiter.limit("10/minute")
async def enrich_artist_watch(
    request: Request,
    artist_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ArtistEnrichWatchResponse:
    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    task_id = uuid.uuid4().hex
    await progress.set_progress(
        task_id, "queued", f"enrichment queued for {artist.name!r}"
    )
    try:
        from app.services.artist_enrichment_worker import (
            enrich_artist_task,
        )

        await enrich_artist_task.kiq(
            artist_id=artist_id,
            progress_id=task_id,
            bypass_cache=True,
        )
    except Exception:
        logger.exception(
            "artist_enrich_watch_schedule_failed",
            artist_id=artist_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Worker unavailable; try again.",
        )
    return ArtistEnrichWatchResponse(task_id=task_id)


@router.get(
    "/{artist_id}/enrich/status",
    response_model=ArtistEnrichStatusResponse,
    summary="[Admin] Poll enrichment task status by task_id.",
)
@limiter.limit("120/minute")
async def enrich_artist_status(
    request: Request,
    artist_id: int,
    task_id: str = Query(..., min_length=1, max_length=128),
    _admin: User = Depends(require_admin),
) -> ArtistEnrichStatusResponse:
    data = await progress.get_progress(task_id)
    if not data:
        return ArtistEnrichStatusResponse(
            status="pending", stage="queued", logs=[]
        )
    stage_raw = data.get("stage")
    stage = str(stage_raw) if isinstance(stage_raw, str) else None
    logs_raw = data.get("logs") or []
    logs = [str(x) for x in logs_raw if isinstance(x, str)]
    status_map = {
        "done": "done",
        "not_found": "not_found",
        "error": "error",
    }
    status_value = status_map.get(stage or "", "pending")
    return ArtistEnrichStatusResponse(
        status=status_value, stage=stage, logs=logs
    )


@router.get(
    "/{artist_id}/tracks",
    response_model=TrackListResponse,
)
async def get_artist_tracks(
    artist_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = ArtistService(db)
    tracks, total = await svc.list_artist_tracks(
        artist_id=artist_id, page=page, size=size
    )
    items = await dedupe_and_build_track_list(db, tracks)
    return TrackListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/supplemental/batch-prompt",
    response_model=ArtistSupplementalBatchPromptResponse,
    summary="[Admin] Generate batch prompt for artist supplemental import.",
)
@limiter.limit("20/minute")
async def artist_supplemental_batch_prompt(
    request: Request,
    data: ArtistSupplementalBatchPromptRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ArtistSupplementalBatchPromptResponse:
    svc = AdminArtistSupplementalService(db)
    prompt, count = await svc.batch_prompt(data.artist_ids)
    return ArtistSupplementalBatchPromptResponse(
        prompt=prompt,
        artist_count=count,
    )


@router.post(
    "/supplemental/batch-import",
    response_model=ArtistSupplementalBatchImportResponse,
    summary="[Admin] Import AI response into artist supplemental text.",
)
@limiter.limit("10/minute")
async def artist_supplemental_batch_import(
    request: Request,
    data: ArtistSupplementalBatchImportRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ArtistSupplementalBatchImportResponse:
    svc = AdminArtistSupplementalService(db)
    imported, errors = await svc.batch_import(data.raw_response)
    await db.commit()
    return ArtistSupplementalBatchImportResponse(
        imported=imported,
        errors=errors,
    )


@router.get(
    "/{artist_id}/supplemental",
    response_model=ArtistSupplementalResponse,
    summary="Get supplemental AI-generated info about an artist.",
)
async def get_artist_supplemental(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArtistSupplementalResponse:
    from datetime import UTC, datetime

    from app.repositories.artist_supplemental_info import (
        ArtistSupplementalInfoRepository,
    )

    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    repo = ArtistSupplementalInfoRepository(db)
    info = await repo.get_by_artist_id(artist_id)
    if info is not None:
        # Let a fresh "fetching" row stay — the worker is still running.
        # A stale "fetching" (>3 min) means the worker crashed; fall
        # through to re-enqueue below.
        if info.status != "fetching":
            return ArtistSupplementalResponse.model_validate(info)
        if info.fetched_at is not None:
            age = (datetime.now(UTC) - info.fetched_at).total_seconds()
            if age < 180:
                return ArtistSupplementalResponse.model_validate(info)

    # Lazy-trigger a fetch only if primary enrichment has already
    # completed (done / failed / not_found) — otherwise we wait for
    # primary to chain into supplemental itself (see
    # ArtistEnrichmentService._schedule_supplemental).
    primary_terminal = artist.enrichment_status in (
        "done",
        "failed",
        "not_found",
    )
    if not primary_terminal:
        return ArtistSupplementalResponse(
            status="pending", content=None, fetched_at=None
        )

    # Seed a fetching row + enqueue the worker. Upsert is idempotent
    # against races (two concurrent GETs race → one wins the task,
    # the other just sees status=fetching).
    row = await repo.upsert(
        artist_id,
        status="fetching",
        content=None,
        fetched_at=datetime.now(UTC),
    )
    await db.commit()

    try:
        from app.services.artist_supplemental_worker import (
            enrich_artist_supplemental_task,
        )

        await enrich_artist_supplemental_task.kiq(
            artist_id=artist_id, force=False
        )
    except Exception:
        logger.exception(
            "artist_supplemental_lazy_enqueue_failed",
            artist_id=artist_id,
        )

    return ArtistSupplementalResponse.model_validate(row)


@router.post(
    "/{artist_id}/supplemental/refresh",
    response_model=ArtistSupplementalResponse,
    summary="[Admin] Force-refresh supplemental AI info for an artist.",
)
@limiter.limit("10/minute")
async def refresh_artist_supplemental(
    request: Request,
    artist_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ArtistSupplementalResponse:
    from app.repositories.artist_supplemental_info import (
        ArtistSupplementalInfoRepository,
    )
    from app.services.artist_supplemental_worker import (
        enrich_artist_supplemental_task,
    )

    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    repo = ArtistSupplementalInfoRepository(db)
    existing = await repo.get_by_artist_id(artist_id)
    row = await repo.upsert(
        artist_id,
        status="fetching",
        content=existing.content if existing else None,
        fetched_at=existing.fetched_at if existing else None,
    )
    await db.commit()

    try:
        await enrich_artist_supplemental_task.kiq(
            artist_id=artist_id, force=True
        )
    except Exception:
        logger.exception(
            "artist_supplemental_refresh_enqueue_failed",
            artist_id=artist_id,
        )
        raise HTTPException(
            status_code=503, detail="Worker unavailable; try again."
        )

    return ArtistSupplementalResponse.model_validate(row)


@router.get(
    "/{artist_id}/similar",
    response_model=ArtistListResponse,
)
async def get_similar_artists(
    artist_id: int,
    limit: int = Query(default=10, le=30),
    db: AsyncSession = Depends(get_db),
):
    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        return ArtistListResponse(items=[], total=0)

    similar = await svc.list_similar_artists_for_discovery(
        artist_id,
        limit=limit,
    )

    return ArtistListResponse(
        items=[
            ArtistResponse.model_validate(a) for a in similar
        ],
        total=len(similar),
    )


@router.post(
    "/{artist_id}/follow",
    response_model=ArtistFollowToggleResponse,
    summary="Toggle follow for an artist.",
)
@limiter.limit("60/minute")
async def toggle_artist_follow(
    request: Request,
    artist_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArtistFollowToggleResponse:
    svc = ArtistFollowService(db)
    try:
        result = await svc.toggle_follow(
            user_id=current_user.id,
            artist_id=artist_id,
        )
        await db.commit()
    except ValueError:
        raise HTTPException(
            status_code=404, detail="Artist not found"
        )
    return ArtistFollowToggleResponse(**result)


@router.get(
    "/{artist_id}/follow/status",
    response_model=ArtistFollowStatusResponse,
    summary="Check if current user follows an artist.",
)
@limiter.limit("120/minute")
async def artist_follow_status(
    request: Request,
    artist_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArtistFollowStatusResponse:
    repo = ArtistFollowRepository(db)
    following = await repo.is_following(
        current_user.id, artist_id
    )
    return ArtistFollowStatusResponse(
        artist_id=artist_id, following=following
    )


@router.get(
    "/{artist_id}/stats/listeners",
    response_model=ArtistListenersResponse,
    summary="Monthly active listeners for an artist.",
)
async def get_artist_listeners(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArtistListenersResponse:
    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(
            status_code=404, detail="Artist not found"
        )
    stats_svc = ArtistStatsService(db)
    return await stats_svc.get_listeners_response(artist_id)
