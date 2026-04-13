import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def test_get_messages_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/chats/1/messages",
    )
    assert r.status_code == 401


async def test_send_message_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/chats/1/messages",
        json={"content": "hello", "type": "text"},
    )
    assert r.status_code == 401


async def test_delete_message_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.delete(
        "/api/v1/messages/1",
    )
    assert r.status_code == 401
