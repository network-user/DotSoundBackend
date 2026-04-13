import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_stats_empty(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 9001)
    resp = await client.get(
        f"/api/v1/users/{user['id']}/stats"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == user["id"]
    assert data["total_tracks"] == 0
    assert data["total_plays"] == 0
    assert data["top_tracks"] == []


async def test_stats_with_tracks(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 9010)
    track = await create_test_track(
        client, "Hit Song", user["id"]
    )
    track_id = track["id"]

    for _ in range(3):
        await client.post(
            f"/api/v1/tracks/{track_id}/play"
        )

    resp = await client.get(
        f"/api/v1/users/{user['id']}/stats"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tracks"] == 1


async def test_stats_top_tracks_order(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 9020)

    ids = []
    for i in range(6):
        t = await create_test_track(
            client, f"Track {i}", user["id"]
        )
        ids.append(t["id"])

    for plays, track_id in enumerate(ids):
        for _ in range(plays):
            await client.post(
                f"/api/v1/tracks/{track_id}/play"
            )

    resp = await client.get(
        f"/api/v1/users/{user['id']}/stats"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tracks"] == 6
    top = data["top_tracks"]
    assert len(top) <= 5
    counts = [t["play_count"] for t in top]
    assert counts == sorted(
        counts, reverse=True
    )


async def test_stats_only_own_tracks(
    client: AsyncClient,
) -> None:
    alice = await create_test_user(
        client, 9002, first_name="Alice"
    )
    bob = await create_test_user(
        client, 9003, first_name="Bob"
    )

    await create_test_track(
        client, "Alice Track", alice["id"]
    )
    await create_test_track(
        client, "Bob Track", bob["id"]
    )

    resp = await client.get(
        f"/api/v1/users/{alice['id']}/stats"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tracks"] == 1
