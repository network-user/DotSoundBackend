import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_toggle_dislike_on_and_off(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70001)
    track = await create_test_track(
        client, "DL1", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    r1 = await client.post(
        f"/api/v1/dislikes/{track['id']}",
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["disliked"] is True

    r2 = await client.post(
        f"/api/v1/dislikes/{track['id']}",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["disliked"] is False


async def test_dislike_nonexistent_track(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70002)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.post(
        "/api/v1/dislikes/99999",
        headers=headers,
    )
    assert r.status_code in (404, 200)


async def test_dislike_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post("/api/v1/dislikes/1")
    assert r.status_code == 401


async def test_dislike_public_endpoint(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70003)
    track = await create_test_track(
        client, "DL2", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.post(
        f"/api/v1/dislikes/{user['id']}"
        f"/{track['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["disliked"] is True


async def test_get_user_dislikes(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70010)
    track = await create_test_track(
        client, "DLGet", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    await client.post(
        f"/api/v1/dislikes/{track['id']}",
        headers=headers,
    )

    r = await client.get(
        f"/api/v1/dislikes/{user['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json() == IsPartialDict(
        total=1,
        items=[IsPartialDict(id=track["id"])],
    )


async def test_get_user_dislikes_requires_auth(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70011)
    r = await client.get(
        f"/api/v1/dislikes/{user['id']}",
    )
    assert r.status_code == 401


async def test_get_user_dislikes_forbidden_other_user(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 70012)
    other = await create_test_user(client, 70013)
    headers = await auth_headers(
        client, other["id"]
    )

    r = await client.get(
        f"/api/v1/dislikes/{owner['id']}",
        headers=headers,
    )
    assert r.status_code == 403


async def test_get_user_dislikes_empty(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 70014)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.get(
        f"/api/v1/dislikes/{user['id']}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["has_more"] is False
