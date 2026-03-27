from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def mock_s3_upload() -> None:
    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value="anon/testkey.mp3",
    ):
        yield


@pytest.mark.anyio
async def test_upload_valid_mp3(client: AsyncClient) -> None:
    audio_bytes = b"\xff\xfb" + b"\x00" * 64
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "Test Track", "artist": "Test Artist"},
        files={
            "file": ("track.mp3", BytesIO(audio_bytes), "audio/mpeg")
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Track"
    assert data["artist"] == "Test Artist"
    assert data["file_key"] == "anon/testkey.mp3"


@pytest.mark.anyio
async def test_upload_invalid_mime(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "Bad File"},
        files={
            "file": ("image.png", BytesIO(b"\x89PNG"), "image/png")
        },
    )
    assert response.status_code == 415


@pytest.mark.anyio
async def test_upload_too_large(client: AsyncClient) -> None:
    big_data = b"\xff\xfb" + b"\x00" * (51 * 1024 * 1024)
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "Huge"},
        files={
            "file": ("big.mp3", BytesIO(big_data), "audio/mpeg")
        },
    )
    assert response.status_code == 413


@pytest.mark.anyio
async def test_upload_no_artist(client: AsyncClient) -> None:
    audio_bytes = b"\xff\xfb" + b"\x00" * 64
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "No Artist"},
        files={
            "file": (
                "track.mp3",
                BytesIO(audio_bytes),
                "audio/mpeg",
            )
        },
    )
    assert response.status_code == 201
    assert response.json()["artist"] is None
