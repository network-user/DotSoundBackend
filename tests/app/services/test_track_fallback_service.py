from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.track_fallback_service import (
    _BLOCK_PREFIX,
    TrackFallbackService,
)

pytestmark = pytest.mark.anyio

_SETTINGS = object()


async def _make_user(session: AsyncSession) -> User:
    u = User(telegram_id=9100, first_name="T")
    session.add(u)
    await session.flush()
    await session.refresh(u)
    return u


async def _make_track(
    session: AsyncSession,
    user: User,
    *,
    title: str = "Song",
    artist: str = "Artist",
    duration_seconds: int = 200,
    source_platform: str = "soundcloud",
    source_url: str = "https://sc.com/1",
    sc_url: str | None = None,
) -> Track:
    t = Track(
        title=title,
        artist=artist,
        duration_seconds=duration_seconds,
        source_platform=source_platform,
        source_url=source_url,
        sc_url=sc_url,
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    session.add(t)
    await session.flush()
    await session.refresh(t)
    return t


def _mock_redis(get_return: bytes | None = None) -> MagicMock:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=get_return)
    redis.set = AsyncMock(return_value=True)
    return redis


@patch("app.core.redis.get_redis_client")
async def test_returns_none_when_no_title(
    _mock_redis_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    track = await _make_track(db_session, user, title="")
    track.title = ""
    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(track)
    assert result is None


@patch("app.core.redis.get_redis_client")
async def test_returns_none_when_no_duration(
    _mock_redis_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    track = await _make_track(db_session, user)
    track.duration_seconds = None
    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(track)
    assert result is None


@patch("app.core.redis.get_redis_client")
async def test_redis_block_returns_none(
    mock_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    mock_factory.return_value = _mock_redis(get_return=b"not_found")
    user = await _make_user(db_session)
    track = await _make_track(db_session, user)
    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(track)
    assert result is None


@patch("app.core.redis.get_redis_client")
async def test_no_candidates_sets_redis_block(
    mock_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    redis = _mock_redis()
    mock_factory.return_value = redis
    user = await _make_user(db_session)
    track = await _make_track(db_session, user, title="Unique Song XYZ")
    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(track)
    assert result is None
    redis.set.assert_awaited_once()
    call_args = redis.set.call_args
    assert call_args[0][0] == f"{_BLOCK_PREFIX}{track.id}"
    assert call_args[1]["ex"] == 3600


@patch("app.core.redis.get_redis_client")
async def test_applies_replacement_from_other_platform(
    mock_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    redis = _mock_redis()
    mock_factory.return_value = redis
    user = await _make_user(db_session)

    original = await _make_track(
        db_session,
        user,
        title="Great Track",
        duration_seconds=180,
        source_platform="soundcloud",
        source_url="https://sc.com/old",
        sc_url="https://soundcloud.com/track/old",
    )
    replacement = await _make_track(
        db_session,
        user,
        title="Great Track",
        duration_seconds=182,
        source_platform="youtube",
        source_url="https://yt.com/new",
    )
    await db_session.commit()

    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(original)

    assert result is not None
    assert result.source_platform == "youtube"
    assert result.source_url == "https://yt.com/new"
    assert result.previous_source_url == "https://sc.com/old"
    assert result.sc_url is None
    redis.set.assert_not_awaited()


@patch("app.core.redis.get_redis_client")
async def test_apply_replacement_clears_sc_url(
    mock_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    """sc_url must be None after replacement to avoid unique constraint violation."""
    redis = _mock_redis()
    mock_factory.return_value = redis
    user = await _make_user(db_session)

    original = await _make_track(
        db_session,
        user,
        title="Unique Bop",
        duration_seconds=200,
        source_platform="soundcloud",
        source_url="https://sc.com/bop",
        sc_url="https://soundcloud.com/bop",
    )
    replacement = await _make_track(
        db_session,
        user,
        title="Unique Bop",
        duration_seconds=200,
        source_platform="bandcamp",
        source_url="https://bc.com/bop",
    )
    await db_session.commit()

    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(original)

    assert result is not None
    assert result.sc_url is None
    assert result.source_platform == "bandcamp"
