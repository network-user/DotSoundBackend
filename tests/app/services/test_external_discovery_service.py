from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.external_discovery_service import (
    ExternalDiscoveryService,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.external_discovery_service"


async def test_discover_no_client_id(
    session: AsyncSession,
) -> None:
    with patch(
        f"{_MOD}.settings"
    ) as mock_settings:
        mock_settings.sc_client_id = ""
        svc = ExternalDiscoveryService(session)
        result = await svc.discover(["rock"])
    assert result == []


async def test_discover_returns_deduplicated(
    session: AsyncSession,
) -> None:
    duplicate = {
        "id": 1,
        "title": "Song",
        "user": {"username": "Artist"},
        "permalink_url": "https://sc.com/song",
        "genre": "rock",
        "artwork_url": None,
        "playback_count": 100,
        "duration": 180000,
    }

    mock_svc = AsyncMock()
    mock_svc.get_trending = AsyncMock(
        return_value=[duplicate]
    )
    mock_svc.search = AsyncMock(
        return_value=[duplicate]
    )

    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(
            f"{_MOD}.SoundCloudService",
            return_value=mock_svc,
        ),
    ):
        mock_settings.sc_client_id = "test_id"
        svc = ExternalDiscoveryService(session)
        result = await svc.discover(["rock"])

    assert len(result) == 1
    assert result[0].title == "Song"
    assert result[0].source == "soundcloud"
    assert result[0].play_count == 100
    assert result[0].duration_seconds == 180


async def test_discover_skips_items_without_id(
    session: AsyncSession,
) -> None:
    mock_svc = AsyncMock()
    mock_svc.get_trending = AsyncMock(
        return_value=[{"title": "No ID track"}]
    )
    mock_svc.search = AsyncMock(return_value=[])

    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(
            f"{_MOD}.SoundCloudService",
            return_value=mock_svc,
        ),
    ):
        mock_settings.sc_client_id = "test_id"
        svc = ExternalDiscoveryService(session)
        result = await svc.discover([])

    assert result == []


async def test_discover_handles_trending_failure(
    session: AsyncSession,
) -> None:
    track = {
        "id": 42,
        "title": "Fallback",
        "user": {"username": "DJ"},
        "permalink_url": "https://sc.com/fb",
        "genre": "pop",
        "artwork_url": None,
        "playback_count": 0,
        "duration": None,
    }

    mock_svc = AsyncMock()
    mock_svc.get_trending = AsyncMock(
        side_effect=Exception("network error")
    )
    mock_svc.search = AsyncMock(return_value=[track])

    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(
            f"{_MOD}.SoundCloudService",
            return_value=mock_svc,
        ),
    ):
        mock_settings.sc_client_id = "test_id"
        svc = ExternalDiscoveryService(session)
        result = await svc.discover(["pop"])

    assert len(result) == 1
    assert result[0].title == "Fallback"
    assert result[0].duration_seconds is None


async def test_discover_limits_to_two_genres(
    session: AsyncSession,
) -> None:
    mock_svc = AsyncMock()
    mock_svc.get_trending = AsyncMock(return_value=[])
    mock_svc.search = AsyncMock(return_value=[])

    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(
            f"{_MOD}.SoundCloudService",
            return_value=mock_svc,
        ),
    ):
        mock_settings.sc_client_id = "test_id"
        svc = ExternalDiscoveryService(session)
        await svc.discover(
            ["rock", "pop", "jazz", "metal"]
        )

    assert mock_svc.search.call_count == 2
