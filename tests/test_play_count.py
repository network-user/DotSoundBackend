from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def _create_track(client: AsyncClient, title: str) -> int:
    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value=f"anon/{title}.mp3",
    ):
        r = await client.post(
            "/api/v1/tracks/upload",
            data={"title": title},
            files={
                "file": (
                    "t.mp3",
                    BytesIO(b"\xff\xfb" + b"\x00" * 64),
                    "audio/mpeg",
                )
            },
        )
    assert r.status_code == 201
    return r.json()["id"]  # type: ignore[no-any-return]


@pytest.mark.anyio
async def test_play_increments_count(client: AsyncClient) -> None:
    track_id = await _create_track(client, "PlayMe")

    r1 = await client.post(f"/api/v1/tracks/{track_id}/play")
    assert r1.status_code == 200
    assert r1.json()["play_count"] == 1

    r2 = await client.post(f"/api/v1/tracks/{track_id}/play")
    assert r2.status_code == 200
    assert r2.json()["play_count"] == 2


@pytest.mark.anyio
async def test_play_not_found(client: AsyncClient) -> None:
    response = await client.post("/api/v1/tracks/99999/play")
    assert response.status_code == 404
