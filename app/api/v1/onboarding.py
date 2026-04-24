from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.onboarding import (
    ArtistBriefResponse,
    CalibrationRequest,
    OnboardingPreferencesRequest,
    OnboardingStatusResponse,
)
from app.schemas.track import TrackResponse
from app.services.onboarding_service import (
    OnboardingService,
)

router = APIRouter(
    prefix="/onboarding", tags=["onboarding"]
)


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
)
async def get_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    return await svc.get_status_response(user)


@router.post("/import-ack")
async def acknowledge_import_prompt(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    await svc.acknowledge_import_prompt(user.id)
    return {"status": "ok"}


@router.get(
    "/genres", response_model=list[str]
)
async def get_genres(
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    return await svc.get_available_genres()


@router.get(
    "/artists",
    response_model=list[ArtistBriefResponse],
)
async def get_artists(
    genres: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    genre_list = (
        [g.strip() for g in genres.split(",")]
        if genres
        else None
    )
    artists = await svc.get_popular_artists(
        genres=genre_list, limit=limit
    )
    return [
        ArtistBriefResponse.model_validate(a)
        for a in artists
    ]


@router.post("/preferences")
async def save_preferences(
    body: OnboardingPreferencesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    await svc.save_preferences(
        user_id=user.id,
        genres=body.genres,
        artist_ids=body.artist_ids,
        moods=body.moods,
    )
    return {"status": "ok"}


@router.get(
    "/calibration",
    response_model=list[TrackResponse],
)
async def get_calibration(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    tracks = await svc.get_calibration_tracks(
        user.id
    )
    return [
        TrackResponse.model_validate(t)
        for t in tracks
    ]


@router.post("/calibration")
async def save_calibration(
    body: CalibrationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    await svc.save_calibration(
        user_id=user.id,
        items=[
            {
                "track_id": i.track_id,
                "liked": i.liked,
            }
            for i in body.items
        ],
    )
    return {"status": "ok"}


@router.post("/complete")
async def complete_onboarding(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OnboardingService(db)
    await svc.complete(user.id)
    return {"status": "ok"}
