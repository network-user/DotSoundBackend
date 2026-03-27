import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.anyio


async def _register_user(client: AsyncClient) -> int:
    resp = await client.post(
        "/api/v1/users",
        json={
            "telegram_id": 9001,
            "first_name": "Stats",
            "username": "statsuser",
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def _upload_track(
    client: AsyncClient,
    user_id: int,
    title: str,
) -> int:
    with (
        patch(
            "app.core.s3.upload_audio",
            new_callable=AsyncMock,
            return_value=f"anon/{title}.mp3",
        ),
        patch(
            "app.core.s3.ensure_bucket_exists",
            new_callable=AsyncMock,
        ),
    ):
        resp = await client.post(
            "/api/v1/tracks/upload",
            data={"title": title, "uploader_id": str(user_id)},
            files={"file": (f"{title}.mp3", b"data", "audio/mpeg")},
        )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.anyio
async def test_stats_empty(client: AsyncClient) -> None:
    user_id = await _register_user(client)
    resp = await client.get(f"/api/v1/users/{user_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == user_id
    assert data["total_tracks"] == 0
    assert data["total_plays"] == 0
    assert data["top_tracks"] == []


@pytest.mark.anyio
async def test_stats_with_tracks(client: AsyncClient) -> None:
    user_id = await _register_user(client)
    track_id = await _upload_track(client, user_id, "Hit Song")

    for _ in range(3):
        await client.post(f"/api/v1/tracks/{track_id}/play")

    resp = await client.get(f"/api/v1/users/{user_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tracks"] == 1
    assert data["total_plays"] == 3
    assert len(data["top_tracks"]) == 1
    assert data["top_tracks"][0]["id"] == track_id
    assert data["top_tracks"][0]["play_count"] == 3


@pytest.mark.anyio
async def test_stats_top_tracks_order(client: AsyncClient) -> None:
    user_id = await _register_user(client)

    ids = []
    for i in range(6):
        tid = await _upload_track(client, user_id, f"Track {i}")
        ids.append(tid)

    for plays, track_id in enumerate(ids):
        for _ in range(plays):
            await client.post(f"/api/v1/tracks/{track_id}/play")

    resp = await client.get(f"/api/v1/users/{user_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tracks"] == 6
    top = data["top_tracks"]
    assert len(top) == 5
    counts = [t["play_count"] for t in top]
    assert counts == sorted(counts, reverse=True)


@pytest.mark.anyio
async def test_stats_only_own_tracks(client: AsyncClient) -> None:
    resp1 = await client.post(
        "/api/v1/users",
        json={"telegram_id": 9002, "first_name": "Alice"},
    )
    resp2 = await client.post(
        "/api/v1/users",
        json={"telegram_id": 9003, "first_name": "Bob"},
    )
    alice_id = resp1.json()["id"]
    bob_id = resp2.json()["id"]

    await _upload_track(client, alice_id, "Alice Track")
    await _upload_track(client, bob_id, "Bob Track")

    resp = await client.get(f"/api/v1/users/{alice_id}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tracks"] == 1
    assert data["top_tracks"][0]["title"] == "Alice Track"
