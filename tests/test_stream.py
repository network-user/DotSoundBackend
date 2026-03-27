from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_stream_track_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks/99999/stream")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_stream_returns_presigned_url(
    client: AsyncClient,
) -> None:
    from io import BytesIO
    from unittest.mock import AsyncMock, patch

    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value="1/abc.mp3",
    ):
        upload = await client.post(
            "/api/v1/tracks/upload",
            data={"title": "StreamMe", "artist": "DJ"},
            files={
                "file": (
                    "t.mp3",
                    BytesIO(b"\xff\xfb" + b"\x00" * 64),
                    "audio/mpeg",
                )
            },
        )
    assert upload.status_code == 201
    track_id = upload.json()["id"]

    with patch(
        "app.core.s3.get_presigned_url",
        new_callable=AsyncMock,
        return_value="https://minio.local/dotsound-audio/1/abc.mp3?X-Amz-Signature=fake",
    ):
        response = await client.get(
            f"/api/v1/tracks/{track_id}/stream"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["track_id"] == track_id
    assert data["url"].startswith("https://")
    assert data["expires_in"] == 3600
