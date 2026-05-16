from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.track_fallback_service import (
    _BLOCK_PREFIX,
    _SC_REFRESH_PREFIX,
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
async def test_returns_replacement_without_mutating_original(
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
    assert result.id == replacement.id
    assert result.source_platform == "youtube"
    await db_session.refresh(original)
    assert original.source_platform == "soundcloud"
    assert original.sc_url is not None
    redis.set.assert_not_awaited()


@patch("app.core.redis.get_redis_client")
async def test_falls_through_to_bandcamp_when_youtube_missing(
    mock_factory: MagicMock,
    db_session: AsyncSession,
) -> None:
    redis = _mock_redis()
    mock_factory.return_value = redis
    user = await _make_user(db_session)

    original = await _make_track(
        db_session,
        user,
        title="Only Bandcamp Match",
        duration_seconds=200,
        source_platform="soundcloud",
        source_url="https://sc.com/bop",
        sc_url="https://soundcloud.com/bop",
    )
    replacement = await _make_track(
        db_session,
        user,
        title="Only Bandcamp Match",
        duration_seconds=205,
        source_platform="bandcamp",
        source_url="https://bc.com/bop",
    )
    await db_session.commit()

    svc = TrackFallbackService(db_session, _SETTINGS)
    result = await svc.find_and_apply_fallback(original)

    assert result is not None
    assert result.id == replacement.id
    assert result.source_platform == "bandcamp"
    await db_session.refresh(original)
    assert original.sc_url is not None


@patch("app.services.soundcloud_service.SoundCloudService")
@patch("app.core.redis.get_redis_client")
async def test_try_refresh_sc_url_noop_when_sc_url_owned_by_other(
    mock_redis_factory: MagicMock,
    mock_sc_class: MagicMock,
    db_session: AsyncSession,
) -> None:
    redis = _mock_redis()
    mock_redis_factory.return_value = redis
    user = await _make_user(db_session)
    taken_url = "https://soundcloud.com/artist/taken"
    await _make_track(
        db_session,
        user,
        title="Holder",
        sc_url=taken_url,
        source_url=taken_url,
    )
    stale = await _make_track(
        db_session,
        user,
        title="Maladoy Prince - Сасавот",
        sc_url="https://soundcloud.com/old/broken",
        source_url="https://soundcloud.com/old/broken",
    )
    stale_id = stale.id
    stale_sc_before = stale.sc_url
    await db_session.commit()

    mock_instance = MagicMock()
    mock_instance.search_best_match = AsyncMock(
        return_value={"permalink_url": taken_url, "id": 999999}
    )
    mock_sc_class.return_value = mock_instance

    svc = TrackFallbackService(db_session, _SETTINGS)
    assert await svc.try_refresh_sc_url(stale) is False

    await db_session.refresh(stale)
    assert stale.sc_url == stale_sc_before
    assert stale.id == stale_id
    mock_instance.search_best_match.assert_awaited_once()
    redis.set.assert_awaited()
    assert redis.set.call_args[0][0] == f"{_SC_REFRESH_PREFIX}{stale_id}"


@patch("app.services.soundcloud_service.SoundCloudService")
@patch("app.core.redis.get_redis_client")
async def test_try_refresh_sc_url_updates_source_url_fields(
    mock_redis_factory: MagicMock,
    mock_sc_class: MagicMock,
    db_session: AsyncSession,
) -> None:
    redis = _mock_redis()
    mock_redis_factory.return_value = redis
    user = await _make_user(db_session)
    stale = await _make_track(
        db_session,
        user,
        title="Broken Song",
        artist="Artist",
        sc_url="https://soundcloud.com/old/broken",
        source_url="https://soundcloud.com/old/broken",
    )
    new_url = "https://soundcloud.com/new/fixed"
    await db_session.commit()

    mock_instance = MagicMock()
    mock_instance.search_best_match = AsyncMock(
        return_value={"permalink_url": new_url, "id": 123456}
    )
    mock_sc_class.return_value = mock_instance

    svc = TrackFallbackService(db_session, _SETTINGS)
    assert await svc.try_refresh_sc_url(stale) is True

    await db_session.refresh(stale)
    assert stale.sc_url == new_url
    assert stale.source_url == new_url
    assert stale.canonical_source_url == new_url
    assert stale.external_id == "123456"


@patch("app.services.soundcloud_service.SoundCloudService")
@patch("app.core.redis.get_redis_client")
async def test_try_refresh_sc_url_can_bypass_no_match_cache(
    mock_redis_factory: MagicMock,
    mock_sc_class: MagicMock,
    db_session: AsyncSession,
) -> None:
    redis = _mock_redis(get_return=b"1")
    mock_redis_factory.return_value = redis
    user = await _make_user(db_session)
    stale = await _make_track(
        db_session,
        user,
        title="Broken Song",
        artist="Artist",
        sc_url="https://soundcloud.com/old/broken",
        source_url="https://soundcloud.com/old/broken",
    )
    new_url = "https://soundcloud.com/new/fixed"
    await db_session.commit()

    mock_instance = MagicMock()
    mock_instance.search_best_match = AsyncMock(
        return_value={"permalink_url": new_url, "id": 123456}
    )
    mock_sc_class.return_value = mock_instance

    svc = TrackFallbackService(db_session, _SETTINGS)
    diagnostics: dict[str, object] = {}
    assert await svc.try_refresh_sc_url(
        stale,
        use_no_match_cache=False,
        diagnostics=diagnostics,
    ) is True

    mock_instance.search_best_match.assert_awaited_once()
    await db_session.refresh(stale)
    assert stale.sc_url == new_url
    assert diagnostics["cache"] == "bypassed"
    assert diagnostics["candidate_found"] is True
    assert diagnostics["candidate_url"] == new_url
    assert diagnostics["refreshed"] is True
