import uuid
from datetime import date, datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, require_admin
from app.models.user import User
from app.repositories.artist import ArtistRepository
from app.schemas.artist import (
    ArtistDetailResponse,
    ArtistListResponse,
    ArtistResolveResponse,
    ArtistResponse,
    ArtistSourceProfileResponse,
)
from app.schemas.artist_supplemental import ArtistSupplementalResponse
from app.schemas.track import (
    TrackListResponse,
    TrackResponse,
)
from app.services import artist_enrichment_progress as progress
from app.services.artist_enrichment_service import (
    ArtistEnrichmentService,
    ArtistNotFound,
)
from app.services.artist_service import ArtistService


class ArtistEnrichWatchResponse(BaseModel):
    task_id: str


class ArtistEnrichStatusResponse(BaseModel):
    status: str
    stage: str | None = None
    logs: list[str] = []

router = APIRouter(
    prefix="/artists", tags=["artists"]
)
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _compute_age(birth: date | None) -> int | None:
    if birth is None:
        return None
    today = datetime.now(timezone.utc).date()
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
        try:
            image_url = await s3.get_presigned_url(
                artist.image_key
            )
        except Exception:
            logger.exception(
                "artist_image_presign_failed",
                artist_id=artist_id,
            )

    source_profiles = _build_source_profiles(
        artist.source_profiles
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
            out.append(
                ArtistSourceProfileResponse.model_validate(
                    entry
                )
            )
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
        items=[
            ArtistResponse.model_validate(a)
            for a in artists
        ],
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
        raise HTTPException(
            status_code=400, detail="Invalid artist name"
        )
    return ArtistResolveResponse(id=artist.id)


@router.get(
    "/{artist_id}",
    response_model=ArtistDetailResponse,
)
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
):
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
        raise HTTPException(
            status_code=404, detail="Artist not found"
        )
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

    existing = await db.execute(
        select(Artist).where(Artist.id == artist_id)
    )
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
        raise HTTPException(
            status_code=404, detail="Artist not found"
        )
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
    stage = (
        str(stage_raw) if isinstance(stage_raw, str) else None
    )
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
    return TrackListResponse(
        items=[
            TrackResponse.model_validate(t)
            for t in tracks
        ],
        total=total,
        page=page,
        size=size,
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
    from app.repositories.artist_supplemental_info import (
        ArtistSupplementalInfoRepository,
    )

    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    repo = ArtistSupplementalInfoRepository(db)
    info = await repo.get_by_artist_id(artist_id)
    if info is None:
        return ArtistSupplementalResponse(
            status="pending", content=None, fetched_at=None
        )
    return ArtistSupplementalResponse.model_validate(info)


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
        return ArtistListResponse(
            items=[], total=0
        )

    all_artists = await svc.list_popular(
        limit=limit * 3
    )
    similar = [
        a
        for a in all_artists
        if a.id != artist_id
    ][:limit]

    return ArtistListResponse(
        items=[
            ArtistResponse.model_validate(a)
            for a in similar
        ],
        total=len(similar),
    )
