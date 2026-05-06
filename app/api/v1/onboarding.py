import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.genre_samples import GenrePreviewQueueResponse
from app.schemas.track import TrackResponse
from app.schemas.onboarding import (
    ActivationEventRequest,
    ArtistBriefResponse,
    CalibrationRequest,
    OnboardingPreferencesRequest,
    OnboardingStatusResponse,
    SmartSkipResponse,
)
from app.services.genre_samples_service import GenreSamplesService
from app.services.onboarding_service import (
    OnboardingService,
)
from app.services.track_response_build import (
    build_track_responses,
    dedupe_and_build_track_list,
)

_activation_logger = structlog.get_logger(
    "app.activation"
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
    "/genres/{genre}/preview-queue",
    response_model=GenrePreviewQueueResponse,
)
async def get_genre_preview_queue(
    genre: str,
    limit: int = 10,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenrePreviewQueueResponse:
    cap = max(1, min(limit, 10))
    svc = GenreSamplesService(db)
    tracks = await svc.get_preview_queue(genre, cap)
    return GenrePreviewQueueResponse(
        items=await dedupe_and_build_track_list(db, tracks),
    )


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
    return await build_track_responses(db, tracks)


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


@router.post(
    "/smart-skip", response_model=SmartSkipResponse
)
async def smart_skip(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SmartSkipResponse:
    svc = OnboardingService(db)
    applied = await svc.apply_smart_default_profile(
        user.id
    )
    return SmartSkipResponse(
        applied_genres=applied.get("genres", []),
        applied_artist_ids=applied.get(
            "artist_ids", []
        ),
        applied_moods=applied.get("moods", []),
    )


@router.post("/activation-event")
async def activation_event(
    body: ActivationEventRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    _activation_logger.info(
        "activation_event",
        event=body.event,
        user_id=user.id,
        meta=body.meta or {},
    )
    return {"status": "ok"}
