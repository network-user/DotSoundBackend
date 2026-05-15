from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.external_providers import ProviderError
from app.services.import_service import ImportService

pytestmark = pytest.mark.anyio

_MOD = "app.services.import_service"


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 3100,
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def test_scan_external_rejects_unknown_source(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = ImportService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.scan_external_playlist(
            user.id, "bandcamp", "https://example.com"
        )

    assert exc.value.status_code == 400


@patch(
    f"{_MOD}.scan_playlist_url",
    new_callable=AsyncMock,
)
async def test_scan_external_success(
    mock_scan: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3101)
    mock_scan.return_value = {
        "kind": "playlist",
        "tracks": [
            {"title": "A", "artist": "X"},
            {"title": "B", "artist": "Y"},
        ],
    }

    svc = ImportService(session)
    job = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/1",
    )

    assert job.status == "ready"
    assert job.source == "yandex_music"
    assert job.total_tracks == 2
    assert job.tracks_data is not None
    assert len(job.tracks_data["tracks"]) == 2


@patch(
    f"{_MOD}.scan_playlist_url",
    new_callable=AsyncMock,
)
async def test_scan_external_private_playlist(
    mock_scan: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3102)
    mock_scan.side_effect = ProviderError(
        "private", "playlist is private"
    )

    svc = ImportService(session)
    job = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/1",
    )

    assert job.status == "failed"
    assert job.tracks_data is not None
    assert job.tracks_data["error_code"] == "private"
    assert job.tracks_data["error_message"] == "playlist is private"
    assert (
        job.tracks_data["source_url"]
        == "https://music.yandex.ru/users/u/playlists/1"
    )


@patch(
    f"{_MOD}.scan_playlist_url",
    new_callable=AsyncMock,
)
async def test_scan_external_unknown_exception_maps_to_unavailable(
    mock_scan: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3103)
    mock_scan.side_effect = RuntimeError("boom")

    svc = ImportService(session)
    job = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/album/1",
    )

    assert job.status == "failed"
    assert (
        job.tracks_data["error_code"] == "provider_unavailable"
    )


@patch(
    f"{_MOD}.scan_playlist_url",
    new_callable=AsyncMock,
)
async def test_scan_external_returns_active_job(
    mock_scan: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3104)
    mock_scan.return_value = {
        "kind": "playlist",
        "tracks": [{"title": "A", "artist": "X"}],
    }

    svc = ImportService(session)
    first = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/1",
    )
    second = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/2",
    )

    assert first.id == second.id
    assert mock_scan.call_count == 1


@patch(
    f"{_MOD}.scan_playlist_url",
    new_callable=AsyncMock,
)
async def test_scan_external_vk_music_stores_kind(
    mock_scan: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3105)
    mock_scan.return_value = {
        "kind": "album",
        "tracks": [{"title": "A", "artist": "X"}],
    }

    svc = ImportService(session)
    u = "https://vk.com/music/album/x"
    job = await svc.scan_external_playlist(
        user.id,
        "vk_music",
        u,
    )

    assert job.status == "ready"
    assert job.source == "vk_music"
    assert job.tracks_data is not None
    assert job.tracks_data["kind"] == "album"
    assert job.tracks_data["source_url"] == u
