from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.repositories.user import UserRepository
from app.services.artist_follow_service import ArtistFollowService

pytestmark = pytest.mark.anyio


class _FakeRedis:
    def __init__(self) -> None:
        self._locked = False

    async def set(
        self,
        _key: str,
        _token: str,
        *,
        nx: bool,
        ex: int,
    ) -> bool:
        assert nx is True
        assert ex > 0
        if self._locked:
            return False
        self._locked = True
        return True

    async def eval(
        self,
        _lua: str,
        _numkeys: int,
        _key: str,
        _token: str,
    ) -> int:
        self._locked = False
        return 1


async def _make_user(
    session: AsyncSession,
    telegram_id: int,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id,
        f"user{telegram_id}",
        "Test",
        None,
    )
    return user.id


async def _make_artist(
    session: AsyncSession,
    artist_id: int,
) -> int:
    artist = Artist(
        id=artist_id,
        name=f"Artist {artist_id}",
        name_normalized=f"artist-{artist_id}",
    )
    session.add(artist)
    await session.flush()
    return artist.id


async def test_toggle_follow_enqueues_station_and_full_sync(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session, 8100)
    artist_id = await _make_artist(db_session, 9100)
    svc = ArtistFollowService(db_session)

    station_kiq = AsyncMock(return_value=None)
    full_kiq = AsyncMock(return_value=None)
    fake_redis = _FakeRedis()

    with (
        patch(
            "app.services.artist_catalog_sync_worker."
            "sync_artist_similar_station_task.kiq",
            station_kiq,
        ),
        patch(
            "app.services.artist_catalog_sync_worker."
            "sync_artist_catalog_task.kiq",
            full_kiq,
        ),
        patch(
            "app.services.artist_follow_service.get_redis_client",
            return_value=fake_redis,
        ),
    ):
        result = await svc.toggle_follow(uid, artist_id)

    assert result["following"] is True
    station_kiq.assert_awaited_once_with(artist_id)
    full_kiq.assert_awaited_once_with(artist_id=artist_id)


async def test_toggle_follow_skips_full_sync_when_catalog_fresh(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session, 8101)
    artist_id = await _make_artist(db_session, 9101)
    svc = ArtistFollowService(db_session)

    fresh_synced_at = datetime.now(UTC) - timedelta(days=1)
    station_kiq = AsyncMock(return_value=None)
    full_kiq = AsyncMock(return_value=None)
    fake_redis = _FakeRedis()

    with (
        patch(
            "app.services.artist_catalog_sync_worker."
            "sync_artist_similar_station_task.kiq",
            station_kiq,
        ),
        patch(
            "app.services.artist_catalog_sync_worker."
            "sync_artist_catalog_task.kiq",
            full_kiq,
        ),
        patch(
            "app.services.artist_follow_service.get_redis_client",
            return_value=fake_redis,
        ),
        patch.object(
            svc._catalog_repo,
            "latest_synced_at_for_artist",
            AsyncMock(return_value=fresh_synced_at),
        ),
    ):
        result = await svc.toggle_follow(uid, artist_id)

    assert result["following"] is True
    station_kiq.assert_awaited_once_with(artist_id)
    full_kiq.assert_not_awaited()
