import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_like_toggle_like_and_unlike(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10001)
    track = await create_test_track(
        client, "LikeTrack", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    r1 = await client.post(
        f"/api/v1/likes/{user['id']}"
        f"/{track['id']}",
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["liked"] is True

    r2 = await client.post(
        f"/api/v1/likes/{user['id']}"
        f"/{track['id']}",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["liked"] is False


async def test_like_nonexistent_track(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10002)
    headers = await auth_headers(
        client, user["id"]
    )
    r = await client.post(
        f"/api/v1/likes/{user['id']}/99999",
        headers=headers,
    )
    assert r.status_code == 404


async def test_get_user_likes(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10003)
    track = await create_test_track(
        client, "LikeGet", user["id"]
    )
    headers = await auth_headers(
        client, user["id"]
    )

    await client.post(
        f"/api/v1/likes/{user['id']}"
        f"/{track['id']}",
        headers=headers,
    )

    r = await client.get(
        f"/api/v1/likes/{user['id']}"
    )
    assert r.status_code == 200
    assert r.json() == IsPartialDict(
        total=1,
        items=[IsPartialDict(id=track["id"])],
    )


async def test_get_user_likes_empty(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10004)
    r = await client.get(
        f"/api/v1/likes/{user['id']}"
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0
