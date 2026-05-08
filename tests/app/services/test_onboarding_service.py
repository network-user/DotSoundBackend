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
    user, _ = await repo.upsert(telegram_id, "u", "Test", None)
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
    await _make_track(db_session, genre="jazz", owner_id=uid)

    svc = OnboardingService(db_session)
    genres = await svc.get_available_genres()

    assert "jazz" in genres
    assert "hip-hop" in genres
    assert len(genres) >= 20


async def test_save_calibration(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(db_session, owner_id=uid)

    svc = OnboardingService(db_session)
    await svc.save_preferences(uid, ["rock"], [], [])

    pref = await svc.save_calibration(
        user_id=uid,
        items=[{"track_id": tid, "liked": True}],
    )
    assert pref.calibration_completed is True


async def test_get_calibration_tracks(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    for _i in range(10):
        await _make_track(
            db_session,
            genre="rock",
            owner_id=uid,
        )

    svc = OnboardingService(db_session)
    await svc.save_preferences(uid, ["rock"], [], [])

    tracks = await svc.get_calibration_tracks(uid, count=5)
    assert len(tracks) == 5


async def test_get_profile_defaults_telegram_user(
    db_session: AsyncSession,
) -> None:
    repo = UserRepository(db_session)
    user, _ = await repo.upsert(700, "alex_dev", "Алексей", "Иванов")

    svc = OnboardingService(db_session)
    defaults = await svc.get_profile_defaults(user)

    assert defaults.suggested_display_name == "Алексей"
    assert defaults.auth_provider == "telegram"
    assert defaults.suggested_initials
    assert defaults.suggested_avatar_url


async def test_get_profile_defaults_email_user(
    db_session: AsyncSession,
) -> None:
    repo = UserRepository(db_session)
    user, _ = await repo.upsert_by_email("anna.smith@example.com")

    svc = OnboardingService(db_session)
    defaults = await svc.get_profile_defaults(user)

    assert defaults.auth_provider == "email"
    assert defaults.suggested_display_name.lower().startswith("anna")


async def test_save_profile_updates_display_name(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session, telegram_id=701)
    repo = UserRepository(db_session)
    user = await repo.get_by_id(uid)
    assert user is not None

    svc = OnboardingService(db_session)
    response = await svc.save_profile(
        user,
        display_name="Новое Имя",
        locale="ru-RU",
        use_default_avatar=False,
    )

    assert response.display_name == "Новое Имя"
    assert response.profile_completed is True
    assert response.avatar_url is not None

    refreshed = await repo.get_by_id(uid)
    assert refreshed is not None
    assert refreshed.display_name == "Новое Имя"
    assert refreshed.locale == "ru-RU"


async def test_save_profile_locale_only(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session, telegram_id=702)
    repo = UserRepository(db_session)
    user = await repo.get_by_id(uid)
    assert user is not None

    svc = OnboardingService(db_session)
    await svc.save_profile(
        user,
        display_name=None,
        locale="en-US",
        use_default_avatar=False,
    )

    refreshed = await repo.get_by_id(uid)
    assert refreshed is not None
    assert refreshed.locale == "en-US"


async def test_save_taste_swipe_batch_persists_likes(
    db_session: AsyncSession,
) -> None:
    from app.repositories.like import LikeRepository
    from app.schemas.onboarding import TasteSwipeDecision

    uid = await _make_user(db_session, telegram_id=703)
    tid_a = await _make_track(db_session, genre="rock", owner_id=uid)
    tid_b = await _make_track(db_session, genre="pop", owner_id=uid)
    tid_c = await _make_track(db_session, genre="jazz", owner_id=uid)

    svc = OnboardingService(db_session)
    saved = await svc.save_taste_swipe_batch(
        uid,
        [
            TasteSwipeDecision(track_id=tid_a, decision="like"),
            TasteSwipeDecision(track_id=tid_b, decision="dislike"),
            TasteSwipeDecision(track_id=tid_c, decision="skip"),
        ],
    )
    assert saved == 2

    like_repo = LikeRepository(db_session)
    assert await like_repo.get(uid, tid_a) is not None
    assert await like_repo.get(uid, tid_b) is None


async def test_save_taste_swipe_batch_empty(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session, telegram_id=704)
    svc = OnboardingService(db_session)
    saved = await svc.save_taste_swipe_batch(uid, [])
    assert saved == 0


async def test_bootstrap_returns_combined_payload(
    db_session: AsyncSession,
) -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    uid = await _make_user(db_session, telegram_id=705)
    for genre in ("pop", "rock", "jazz"):
        await _make_track(db_session, genre=genre, owner_id=uid)
    repo = UserRepository(db_session)
    user = await repo.get_by_id(uid)
    assert user is not None

    with patch(
        "app.services.onboarding_service." "preflight_telegram_profile_music",
        new_callable=AsyncMock,
    ) as mock_pf:
        mock_pf.return_value = MagicMock(
            can_import_from_telegram=False,
            has_telegram_profile_music=None,
        )
        svc = OnboardingService(db_session)
        bootstrap = await svc.bootstrap(user)

    assert bootstrap.status is not None
    assert bootstrap.profile_defaults is not None
    assert bootstrap.profile_defaults.suggested_display_name
    assert isinstance(bootstrap.genre_bubbles, list)


async def test_smart_skip_uses_locale_seed(
    db_session: AsyncSession,
) -> None:
    repo = UserRepository(db_session)
    user, _ = await repo.upsert(706, "u706", "RuUser", None)
    user.locale = "ru-RU"
    await db_session.flush()
    for genre in ("pop", "rock", "indie", "jazz", "metal"):
        await _make_track(db_session, genre=genre, owner_id=user.id)

    svc = OnboardingService(db_session)
    applied = await svc.apply_smart_default_profile(user.id)
    assert len(applied["genres"]) <= 5
    assert applied["genres"]
