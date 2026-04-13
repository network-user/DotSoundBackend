from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.soundcloud_service import (
    SoundCloudService,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.soundcloud_service"


async def test_search_no_client_id(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)

    with pytest.raises(HTTPException) as exc:
        await svc.search("test")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = (
        MagicMock()
    )
    mock_response.json.return_value = {
        "collection": [
            {
                "kind": "track",
                "streamable": True,
                "title": "Song",
            },
            {
                "kind": "playlist",
                "streamable": True,
            },
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    tracks = await svc.search("test")

    assert len(tracks) == 1
    assert tracks[0]["title"] == "Song"


async def test_resolve_url_no_client_id(
    session: AsyncSession,
) -> None:
    svc = SoundCloudService("", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url(
            "https://soundcloud.com/x"
        )

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_not_found(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url(
            "https://soundcloud.com/x/y"
        )

    assert exc.value.status_code == 404


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_search_401_expired_key(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.search("test")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_expired_key(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.resolve_url("https://sc.com/x")

    assert exc.value.status_code == 503


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_resolve_url_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "id": 123,
        "title": "Track",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    result = await svc.resolve_url(
        "https://sc.com/x"
    )

    assert result["title"] == "Track"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_no_transcoding(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {"transcodings": []},
        "track_authorization": "",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=resolve_resp
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_stream_info(
            "https://sc.com/x"
        )

    assert exc.value.status_code == 422


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_info_success(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/stream",
                    "format": {
                        "protocol": "progressive"
                    },
                    "snipped": False,
                }
            ]
        },
        "track_authorization": "auth",
    }

    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.raise_for_status = MagicMock()
    stream_resp.json.return_value = {
        "url": "https://cdn/audio.mp3"
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, stream_resp]
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url, protocol = await svc.get_stream_info(
        "https://sc.com/x"
    )

    assert url == "https://cdn/audio.mp3"
    assert protocol == "progressive"


@patch(f"{_MOD}.httpx.AsyncClient")
async def test_get_stream_url(
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    resolve_resp = MagicMock()
    resolve_resp.status_code = 200
    resolve_resp.raise_for_status = MagicMock()
    resolve_resp.json.return_value = {
        "media": {
            "transcodings": [
                {
                    "url": "https://api/s",
                    "format": {
                        "protocol": "progressive"
                    },
                }
            ]
        },
        "track_authorization": "",
    }

    stream_resp = MagicMock()
    stream_resp.status_code = 200
    stream_resp.raise_for_status = MagicMock()
    stream_resp.json.return_value = {
        "url": "https://cdn/a.mp3"
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[resolve_resp, stream_resp]
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_client_cls.return_value = mock_client

    svc = SoundCloudService("test_id", session)
    url = await svc.get_stream_url(
        "https://sc.com/x"
    )

    assert url == "https://cdn/a.mp3"
