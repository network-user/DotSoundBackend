import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.onboarding_service import (
    OnboardingService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 600,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, "u", "Test", None
    )
    return user.id


async def _make_track(
    session: AsyncSession,
    genre: str | None = None,
    owner_id: int | None = None,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="T",
        file_key="k",
        genre=genre,
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_get_status_none(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    svc = OnboardingService(db_session)

    result = await svc.get_status(uid)
    assert result is None


async def test_save_preferences(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    svc = OnboardingService(db_session)

    pref = await svc.save_preferences(
        user_id=uid,
        genres=["rock", "pop"],
        artist_ids=[1, 2],
        moods=["chill"],
    )

    assert pref.onboarding_completed is True
    assert pref.preferred_genres == [
        "rock",
        "pop",
    ]
    assert pref.preferred_moods == ["chill"]


async def test_complete(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    svc = OnboardingService(db_session)

    pref = await svc.complete(uid)
    assert pref.onboarding_completed is True


async def test_get_available_genres(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    await _make_track(
        db_session, genre="jazz", owner_id=uid
    )

    svc = OnboardingService(db_session)
    genres = await svc.get_available_genres()

    assert "jazz" in genres
    assert "hip-hop" in genres
    assert len(genres) >= 20


async def test_save_calibration(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(
        db_session, owner_id=uid
    )

    svc = OnboardingService(db_session)
    await svc.save_preferences(
        uid, ["rock"], [], []
    )

    pref = await svc.save_calibration(
        user_id=uid,
        items=[
            {"track_id": tid, "liked": True}
        ],
    )
    assert pref.calibration_completed is True


async def test_get_calibration_tracks(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    for i in range(10):
        await _make_track(
            db_session,
            genre="rock",
            owner_id=uid,
        )

    svc = OnboardingService(db_session)
    await svc.save_preferences(
        uid, ["rock"], [], []
    )

    tracks = await svc.get_calibration_tracks(
        uid, count=5
    )
    assert len(tracks) == 5
