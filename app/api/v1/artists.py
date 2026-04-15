from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.artist import (
    ArtistDetailResponse,
    ArtistListResponse,
    ArtistResponse,
)
from app.schemas.track import (
    TrackListResponse,
    TrackResponse,
)
from app.services.artist_service import (
    ArtistService,
)

router = APIRouter(
    prefix="/artists", tags=["artists"]
)


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


@router.get(
    "/{artist_id}",
    response_model=ArtistDetailResponse,
)
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException

    svc = ArtistService(db)
    artist = await svc.get_by_id(artist_id)
    if not artist:
        raise HTTPException(
            status_code=404,
            detail="Artist not found",
        )
    from app.repositories.artist import (
        ArtistRepository,
    )

    repo = ArtistRepository(db)
    track_ids = await repo.get_artist_track_ids(
        artist_id
    )
    return ArtistDetailResponse(
        id=artist.id,
        name=artist.name,
        image_key=artist.image_key,
        source=artist.source,
        bio=artist.bio,
        created_at=artist.created_at,
        track_count=len(track_ids),
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
    from app.repositories.artist import (
        ArtistRepository,
    )
    from app.repositories.track import (
        TrackRepository,
    )

    artist_repo = ArtistRepository(db)
    track_ids = await artist_repo.get_artist_track_ids(
        artist_id, limit=500
    )

    if not track_ids:
        return TrackListResponse(
            items=[], total=0, page=page, size=size
        )

    track_repo = TrackRepository(db)
    from sqlalchemy import select

    from app.models.track import Track

    offset = (page - 1) * size
    result = await db.execute(
        select(Track)
        .where(
            Track.id.in_(track_ids),
            Track.is_active.is_(True),
            Track.is_public.is_(True),
        )
        .order_by(Track.play_count.desc())
        .offset(offset)
        .limit(size)
    )
    tracks = list(result.scalars().all())

    from sqlalchemy import func

    total_result = await db.execute(
        select(func.count()).where(
            Track.id.in_(track_ids),
            Track.is_active.is_(True),
            Track.is_public.is_(True),
        )
    )
    total = total_result.scalar_one()

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
