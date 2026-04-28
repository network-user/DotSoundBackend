import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_add_and_get_comments(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 400001, first_name="Commenter"
    )
    t = await create_test_track(
        client, "Song", u["id"]
    )
    headers = await auth_headers(
        client, u["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{t['id']}/comments",
        json={"text": "Great song!"},
        headers=headers,
    )
    assert r.status_code == 200
    comment_id = r.json()["id"]

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/comments",
        headers=headers,
    )
    assert r.status_code == 200
    assert any(
        c["id"] == comment_id for c in r.json()
    )


async def test_non_owner_cannot_pin(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(
        client, 400002, first_name="Owner"
    )
    other = await create_test_user(
        client, 400003, first_name="Other"
    )
    t = await create_test_track(
        client, "Track", owner["id"]
    )
    other_headers = await auth_headers(
        client, other["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{t['id']}/comments",
        json={"text": "comment"},
        headers=other_headers,
    )
    cid = r.json()["id"]

    r = await client.post(
        f"/api/v1/comments/{cid}/pin",
        headers=other_headers,
    )
    assert r.status_code == 403


async def test_comments_disabled(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 400010, first_name="Author"
    )
    t = await create_test_track(
        client, "NoComments", u["id"]
    )
    headers = await auth_headers(
        client, u["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{t['id']}/comments",
        json={"text": "test"},
        headers=headers,
    )
    assert r.status_code == 200


async def test_vote_comment(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 400020, first_name="Voter"
    )
    t = await create_test_track(
        client, "Voteable", u["id"]
    )
    headers = await auth_headers(
        client, u["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{t['id']}/comments",
        json={"text": "nice"},
        headers=headers,
    )
    cid = r.json()["id"]

    r = await client.post(
        f"/api/v1/comments/{cid}/vote",
        json={"is_like": True},
        headers=headers,
    )
    assert r.status_code == 200

    r = await client.delete(
        f"/api/v1/comments/{cid}/vote",
        headers=headers,
    )
    assert r.status_code == 200


async def test_comments_private_track_forbidden(
    client: AsyncClient,
) -> None:
    u = await create_test_user(
        client, 400030, first_name="PrivateOwner"
    )
    t = await create_test_track(
        client, "PrivateSong", u["id"]
    )
    headers = await auth_headers(
        client, u["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{t['id']}",
        json={"is_public": False},
        headers=headers,
    )
    assert r.status_code == 200

    r = await client.post(
        f"/api/v1/tracks/{t['id']}/comments",
        json={"text": "nope"},
        headers=headers,
    )
    assert r.status_code == 403

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/comments",
        headers=headers,
    )
    assert r.status_code == 403
