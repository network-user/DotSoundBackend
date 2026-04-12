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


async def test_saved_chat_is_private_per_user(
    client: AsyncClient,
) -> None:
    u1 = await create_test_user(
        client, 200101, first_name="SavedA"
    )
    u2 = await create_test_user(
        client, 200102, first_name="SavedB"
    )
    headers_u1 = await auth_headers(
        client, u1["id"]
    )
    headers_u2 = await auth_headers(
        client, u2["id"]
    )

    saved_u1 = await client.get(
        "/api/v1/chats/saved",
        headers=headers_u1,
    )
    saved_u2 = await client.get(
        "/api/v1/chats/saved",
        headers=headers_u2,
    )

    assert saved_u1.status_code == 200
    assert saved_u2.status_code == 200
    assert (
        saved_u1.json()["conversation"]["id"]
        != saved_u2.json()["conversation"]["id"]
    )

    conv_id = saved_u1.json()["conversation"]["id"]
    send_u1 = await client.post(
        f"/api/v1/chats/{conv_id}/messages",
        json={"content": "private note"},
        headers=headers_u1,
    )
    assert send_u1.status_code == 200

    list_u2 = await client.get(
        f"/api/v1/chats/{conv_id}/messages",
        headers=headers_u2,
    )
    assert list_u2.status_code == 403


async def test_saved_chat_cannot_add_members(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(
        client, 200103, first_name="Owner"
    )
    other = await create_test_user(
        client, 200104, first_name="Other"
    )
    headers = await auth_headers(
        client, owner["id"]
    )

    saved = await client.get(
        "/api/v1/chats/saved",
        headers=headers,
    )
    conv_id = saved.json()["conversation"]["id"]

    response = await client.post(
        f"/api/v1/chats/{conv_id}/members",
        json={"user_id": other["id"]},
        headers=headers,
    )

    assert response.status_code == 400
