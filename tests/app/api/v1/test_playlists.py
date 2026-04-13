import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_create_and_get_playlist(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20001)
    headers = await auth_headers(
        client, owner["id"]
    )

    r = await client.post(
        "/api/v1/playlists",
        json={
            "name": "My Mix",
            "is_public": True,
        },
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Mix"
    playlist_id = data["id"]

    r2 = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json() == IsPartialDict(
        name="My Mix", tracks=[],
    )


async def test_add_and_remove_track(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20002)
    track = await create_test_track(
        client, "pl_track", owner["id"]
    )
    headers = await auth_headers(
        client, owner["id"]
    )

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Mix"},
        headers=headers,
    )
    playlist_id = pl.json()["id"]

    r_add = await client.post(
        f"/api/v1/playlists/{playlist_id}/tracks",
        json={
            "track_id": track["id"],
            "position": 0,
        },
        headers=headers,
    )
    assert r_add.status_code == 204

    r_get = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert len(r_get.json()["tracks"]) == 1

    r_rm = await client.delete(
        f"/api/v1/playlists/{playlist_id}"
        f"/tracks/{track['id']}",
        headers=headers,
    )
    assert r_rm.status_code == 204

    r_get2 = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r_get2.json()["tracks"] == []


async def test_delete_playlist(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20003)
    headers = await auth_headers(
        client, owner["id"]
    )

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Temp"},
        headers=headers,
    )
    playlist_id = pl.json()["id"]

    r = await client.delete(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r.status_code == 204

    r2 = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r2.status_code == 404


async def test_forbidden_update(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20004)
    other = await create_test_user(client, 20005)
    owner_headers = await auth_headers(
        client, owner["id"]
    )
    other_headers = await auth_headers(
        client, other["id"]
    )

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Private"},
        headers=owner_headers,
    )
    playlist_id = pl.json()["id"]

    r = await client.put(
        f"/api/v1/playlists/{playlist_id}",
        json={"name": "Hacked"},
        headers=other_headers,
    )
    assert r.status_code == 403
