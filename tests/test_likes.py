from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def _create_user(client: AsyncClient, tg_id: int) -> int:
    r = await client.post(
        "/api/v1/users",
        json={
            "telegram_id": tg_id,
            "first_name": "User",
            "username": None,
            "last_name": None,
        },
    )
    assert r.status_code == 200
    return r.json()["id"]  # type: ignore[no-any-return]


async def _create_track(client: AsyncClient) -> int:
    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value="anon/like_test.mp3",
    ):
        r = await client.post(
            "/api/v1/tracks/upload",
            data={"title": "LikeTrack"},
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
async def test_like_toggle_like_and_unlike(
    client: AsyncClient,
) -> None:
    user_id = await _create_user(client, 10001)
    track_id = await _create_track(client)

    r1 = await client.post(
        f"/api/v1/likes/{user_id}/{track_id}"
    )
    assert r1.status_code == 200
    assert r1.json()["liked"] is True

    r2 = await client.post(
        f"/api/v1/likes/{user_id}/{track_id}"
    )
    assert r2.status_code == 200
    assert r2.json()["liked"] is False


@pytest.mark.anyio
async def test_like_nonexistent_track(
    client: AsyncClient,
) -> None:
    user_id = await _create_user(client, 10002)
    r = await client.post(f"/api/v1/likes/{user_id}/99999")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_user_likes(client: AsyncClient) -> None:
    user_id = await _create_user(client, 10003)
    track_id = await _create_track(client)

    await client.post(f"/api/v1/likes/{user_id}/{track_id}")

    r = await client.get(f"/api/v1/likes/{user_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == track_id


@pytest.mark.anyio
async def test_get_user_likes_empty(
    client: AsyncClient,
) -> None:
    user_id = await _create_user(client, 10004)
    r = await client.get(f"/api/v1/likes/{user_id}")
    assert r.status_code == 200
    assert r.json()["total"] == 0
