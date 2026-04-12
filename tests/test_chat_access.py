import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_non_member_cannot_read_messages(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/chats/9999/messages"
    )
    assert r.status_code in (401, 403)


async def test_non_member_cannot_send_message(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/chats/9999/messages",
        json={"content": "hello"},
    )
    assert r.status_code in (401, 403)


async def test_create_dm_and_send(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 100001, first_name="Alice"
    )
    u2 = await create_test_user(
        client, 100002, first_name="Bob"
    )
    headers = await auth_headers(
        client, u1["id"]
    )

    r = await client.post(
        "/api/v1/chats",
        json={"target_user_id": u2["id"]},
        headers=headers,
    )
    assert r.status_code == 200
    conv_id = r.json()["conversation"]["id"]

    r = await client.post(
        f"/api/v1/chats/{conv_id}/messages",
        json={"content": "Hi Bob!"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Hi Bob!"


async def test_delete_message_for_all(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 200001, first_name="X"
    )
    u2 = await create_test_user(
        client, 200002, first_name="Y"
    )
    headers = await auth_headers(
        client, u1["id"]
    )

    r = await client.post(
        "/api/v1/chats",
        json={"target_user_id": u2["id"]},
        headers=headers,
    )
    conv_id = r.json()["conversation"]["id"]

    r = await client.post(
        f"/api/v1/chats/{conv_id}/messages",
        json={"content": "to delete"},
        headers=headers,
    )
    msg_id = r.json()["id"]

    r = await client.delete(
        f"/api/v1/messages/{msg_id}",
        headers=headers,
    )
    assert r.status_code == 200

    r = await client.get(
        f"/api/v1/chats/{conv_id}/messages",
        headers=headers,
    )
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert msg_id not in ids
