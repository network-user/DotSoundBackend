import structlog
from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.genre_samples import GenrePreviewQueueResponse
from app.schemas.onboarding import (
    ActivationEventRequest,
    ArtistBriefResponse,
    ArtistPreviewQueueResponse,
    CalibrationRequest,
    OnboardingBootstrapResponse,
    OnboardingCompleteRequest,
    OnboardingPreferencesRequest,
    OnboardingProfileSubmitRequest,
    OnboardingProfileSubmitResponse,
    OnboardingStatusResponse,
    ProfileDefaultsResponse,
    SeedTracksRequest,
    SeedTracksResponse,
    SmartSkipResponse,
    TasteSwipeBatchRequest,
    TasteSwipeBatchResponse,
)
from app.schemas.track import TrackResponse
from app.services.genre_samples_service import GenreSamplesService
from app.services.onboarding_service import (
    OnboardingService,
)
from app.services.track_response_build import (
    build_track_responses,
    dedupe_and_build_track_list,
)

_activation_logger = structlog.get_logger("app.activation")

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
)
async def get_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    svc = OnboardingService(db)
    return await svc.get_status_response(user)


@router.get(
    "/bootstrap",
    response_model=OnboardingBootstrapResponse,
)
async def get_bootstrap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingBootstrapResponse:
    """Single-shot payload that powers the new onboarding wizard.

    Bundles status + suggested profile defaults + the locale
    curated genre bubbles + whether to show the import CTA.
    """
    svc = OnboardingService(db)
    return await svc.bootstrap(user)


@router.get(
    "/profile-defaults",
    response_model=ProfileDefaultsResponse,
)
async def get_profile_defaults(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileDefaultsResponse:
    svc = OnboardingService(db)
    return await svc.get_profile_defaults(user)


@router.post(
    "/profile",
    response_model=OnboardingProfileSubmitResponse,
)
async def submit_profile(
    body: OnboardingProfileSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProfileSubmitResponse:
    svc = OnboardingService(db)
    return await svc.save_profile(
        user,
        display_name=body.display_name,
        locale=body.locale,
        use_default_avatar=body.use_default_avatar,
    )


@router.post("/import-ack")
async def acknowledge_import_prompt(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = OnboardingService(db)
    await svc.acknowledge_import_prompt(user.id)
    return {"status": "ok"}


@router.post("/tutorial-ack")
async def acknowledge_tutorial(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = OnboardingService(db)
    await svc.acknowledge_tutorial(user.id)
    return {"status": "ok"}


@router.post("/replay")
@limiter.limit("3/minute")
async def replay_onboarding(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """User-facing reset: clear preferences, dislikes and tutorial
    state so the onboarding wizard runs again and recommendations
    are rebuilt from scratch.
    """
    svc = OnboardingService(db)
    await svc.replay_onboarding(user.id)
    return {"status": "ok"}


@router.post(
    "/seed-tracks",
    response_model=SeedTracksResponse,
)
@limiter.limit("5/minute")
async def seed_tracks(
    request: Request,
    body: SeedTracksRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SeedTracksResponse:
    """Like a batch of tracks the user picked in the onboarding
    search panel. Used to bootstrap the library + taste signal in
    one tap.
    """
    svc = OnboardingService(db)
    liked, skipped = await svc.seed_tracks_from_search(
        user_id=user.id,
        track_ids=body.track_ids,
    )
    return SeedTracksResponse(liked=liked, skipped=skipped)


@router.get("/genres", response_model=list[str])
async def get_genres(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
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
) -> list[ArtistBriefResponse]:
    svc = OnboardingService(db)
    genre_list = [g.strip() for g in genres.split(",")] if genres else None
    artists = await svc.get_popular_artists(genres=genre_list, limit=limit)
    return [ArtistBriefResponse.model_validate(a) for a in artists]


@router.get(
    "/artists/{artist_id}/preview-queue",
    response_model=ArtistPreviewQueueResponse,
)
async def get_artist_preview_queue(
    artist_id: int,
    limit: int = 10,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtistPreviewQueueResponse:
    cap = max(1, min(limit, 10))
    svc = OnboardingService(db)
    tracks = await svc.get_artist_preview_queue(artist_id, cap)
    return ArtistPreviewQueueResponse(
        items=await dedupe_and_build_track_list(db, tracks),
    )


@router.post("/preferences")
async def save_preferences(
    body: OnboardingPreferencesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
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
) -> list[TrackResponse]:
    svc = OnboardingService(db)
    tracks = await svc.get_calibration_tracks(user.id)
    return await build_track_responses(db, tracks)


@router.get(
    "/taste-swipe",
    response_model=list[TrackResponse],
)
async def get_taste_swipe_tracks(
    count: int = 5,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """Return ordered tracks for the swipe step.

    The order is provided by PrivateCore policy
    (``order_taste_swipe_tracks``) so the first card is the
    safest bet, and follow-ups rotate genre / language.
    """
    cap = max(3, min(count, 8))
    svc = OnboardingService(db)
    tracks = await svc.get_calibration_tracks(user.id, count=cap)
    return await build_track_responses(db, tracks)


@router.post("/calibration")
async def save_calibration(
    body: CalibrationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
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


@router.post(
    "/taste-swipe",
    response_model=TasteSwipeBatchResponse,
)
async def save_taste_swipe(
    body: TasteSwipeBatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TasteSwipeBatchResponse:
    svc = OnboardingService(db)
    saved = await svc.save_taste_swipe_batch(
        user.id,
        body.decisions,
    )
    return TasteSwipeBatchResponse(
        saved=saved,
        swipe_total=len(body.decisions),
    )


@router.post("/complete")
async def complete_onboarding(
    body: OnboardingCompleteRequest | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Finalize onboarding. The disclosure under the final "Готово"
    button asks the user to confirm 18+ and accept Terms + Privacy
    of the displayed version; clients send that version here so the
    server records implicit acceptance in the same call.
    """
    svc = OnboardingService(db)
    await svc.complete(
        user.id,
        legal_accepted_version=(
            body.legal_accepted_version if body else None
        ),
    )
    return {"status": "ok"}


@router.post("/smart-skip", response_model=SmartSkipResponse)
async def smart_skip(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SmartSkipResponse:
    svc = OnboardingService(db)
    enabled = await svc.is_smart_skip_enabled()
    applied = await svc.apply_smart_default_profile(user.id)
    return SmartSkipResponse(
        applied_genres=applied.get("genres", []),
        applied_artist_ids=applied.get("artist_ids", []),
        applied_moods=applied.get("moods", []),
        enabled=enabled,
    )


@router.post("/activation-event")
async def activation_event(
    body: ActivationEventRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    svc = OnboardingService(db)
    merged_meta = await svc.process_activation_event(
        user_id=user.id,
        event=body.event,
        meta=body.meta,
    )
    _activation_logger.info(
        "activation_event",
        event=body.event,
        user_id=user.id,
        meta=merged_meta,
    )
    return {"status": "ok"}
