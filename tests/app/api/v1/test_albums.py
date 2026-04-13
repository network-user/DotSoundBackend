import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_create_album_success(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60001)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/albums",
        json={"title": "My Album"},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json() == IsPartialDict(
        title="My Album",
        owner_id=user["id"],
        is_public=True,
    )


async def test_create_album_missing_title(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60002)
    headers = await auth_headers(client, user["id"])
    r = await client.post(
        "/api/v1/albums",
        json={},
        headers=headers,
    )
    assert r.status_code == 422


async def test_create_album_unauthorized(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/albums",
        json={"title": "Unauthorized Album"},
    )
    assert r.status_code == 401


async def test_get_album_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/albums/99999")
    assert r.status_code == 404


async def test_get_album_success(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60003)
    headers = await auth_headers(client, user["id"])
    create_r = await client.post(
        "/api/v1/albums",
        json={"title": "Fetchable Album"},
        headers=headers,
    )
    album_id = create_r.json()["id"]

    r = await client.get(
        f"/api/v1/albums/{album_id}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == IsPartialDict(
        title="Fetchable Album",
        tracks=[],
    )


async def test_add_track_to_album(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60004)
    headers = await auth_headers(client, user["id"])
    track = await create_test_track(
        client, "Album Track", uploader_id=user["id"]
    )
    create_r = await client.post(
        "/api/v1/albums",
        json={"title": "Track Album"},
        headers=headers,
    )
    album_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/albums/{album_id}"
        f"/tracks/{track['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["track_id"] == track["id"]


async def test_delete_album(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60005)
    headers = await auth_headers(client, user["id"])
    create_r = await client.post(
        "/api/v1/albums",
        json={"title": "Deletable Album"},
        headers=headers,
    )
    album_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/albums/{album_id}",
        headers=headers,
    )
    assert r.status_code == 204
