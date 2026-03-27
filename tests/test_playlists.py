from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def _create_user(client: AsyncClient, tg_id: int) -> int:
    r = await client.post(
        "/api/v1/users",
        json={
            "telegram_id": tg_id,
            "first_name": "PL",
            "username": None,
            "last_name": None,
        },
    )
    assert r.status_code == 200
    return r.json()["id"]  # type: ignore[no-any-return]


async def _create_track(client: AsyncClient, key: str) -> int:
    with patch(
        "app.core.s3.upload_audio",
        new_callable=AsyncMock,
        return_value=f"anon/{key}.mp3",
    ):
        r = await client.post(
            "/api/v1/tracks/upload",
            data={"title": key},
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
async def test_create_and_get_playlist(
    client: AsyncClient,
) -> None:
    owner_id = await _create_user(client, 20001)

    r = await client.post(
        "/api/v1/playlists",
        json={"name": "My Mix", "is_public": True},
        params={"owner_id": owner_id},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Mix"
    playlist_id = data["id"]

    r2 = await client.get(f"/api/v1/playlists/{playlist_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "My Mix"
    assert r2.json()["tracks"] == []


@pytest.mark.anyio
async def test_add_and_remove_track(
    client: AsyncClient,
) -> None:
    owner_id = await _create_user(client, 20002)
    track_id = await _create_track(client, "pl_track")

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Mix"},
        params={"owner_id": owner_id},
    )
    playlist_id = pl.json()["id"]

    r_add = await client.post(
        f"/api/v1/playlists/{playlist_id}/tracks",
        json={"track_id": track_id, "position": 0},
        params={"requester_id": owner_id},
    )
    assert r_add.status_code == 204

    r_get = await client.get(
        f"/api/v1/playlists/{playlist_id}"
    )
    assert len(r_get.json()["tracks"]) == 1

    r_rm = await client.delete(
        f"/api/v1/playlists/{playlist_id}/tracks/{track_id}",
        params={"requester_id": owner_id},
    )
    assert r_rm.status_code == 204

    r_get2 = await client.get(
        f"/api/v1/playlists/{playlist_id}"
    )
    assert r_get2.json()["tracks"] == []


@pytest.mark.anyio
async def test_delete_playlist(client: AsyncClient) -> None:
    owner_id = await _create_user(client, 20003)

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Temp"},
        params={"owner_id": owner_id},
    )
    playlist_id = pl.json()["id"]

    r = await client.delete(
        f"/api/v1/playlists/{playlist_id}",
        params={"requester_id": owner_id},
    )
    assert r.status_code == 204

    r2 = await client.get(f"/api/v1/playlists/{playlist_id}")
    assert r2.status_code == 404


@pytest.mark.anyio
async def test_forbidden_update(client: AsyncClient) -> None:
    owner_id = await _create_user(client, 20004)
    other_id = await _create_user(client, 20005)

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Private"},
        params={"owner_id": owner_id},
    )
    playlist_id = pl.json()["id"]

    r = await client.put(
        f"/api/v1/playlists/{playlist_id}",
        json={"name": "Hacked"},
        params={"requester_id": other_id},
    )
    assert r.status_code == 403
