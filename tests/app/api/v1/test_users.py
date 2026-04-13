import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_register_new_user(
    client: AsyncClient,
) -> None:
    payload = {
        "telegram_id": 123456789,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
    }
    response = await client.post(
        "/api/v1/users", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == 123456789
    assert data["username"] == "testuser"
    assert data["first_name"] == "Test"
    assert data["is_active"] is True


async def test_register_same_user_twice(
    client: AsyncClient,
) -> None:
    payload = {
        "telegram_id": 111222333,
        "username": "dup",
        "first_name": "Dup",
        "last_name": None,
    }
    r1 = await client.post(
        "/api/v1/users", json=payload
    )
    assert r1.status_code == 200

    payload["username"] = "dup_updated"
    r2 = await client.post(
        "/api/v1/users", json=payload
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]
    assert (
        r2.json()["username"] == "dup_updated"
    )


async def test_get_user_not_found(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/users/99999"
    )
    assert response.status_code == 404


async def test_get_user_by_id(
    client: AsyncClient,
) -> None:
    payload = {
        "telegram_id": 987654321,
        "username": "getme",
        "first_name": "Get",
        "last_name": "Me",
    }
    created = await client.post(
        "/api/v1/users", json=payload
    )
    user_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/users/{user_id}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == user_id
