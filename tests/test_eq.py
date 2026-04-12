import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user


@pytest.mark.anyio
async def test_eq_get_default(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700001)
    headers = await auth_headers(
        client, user["id"]
    )

    response = await client.get(
        "/api/v1/users/me/eq",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "preset": "Flat",
        "bands": [0, 0, 0, 0, 0, 0, 0, 0],
    }


@pytest.mark.anyio
async def test_eq_save_and_get(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700002)
    headers = await auth_headers(
        client, user["id"]
    )

    payload = {
        "preset": "Rock",
        "bands": [4, 3, 1, 0, -1, 1, 3, 4],
    }
    save_response = await client.put(
        "/api/v1/users/me/eq",
        json=payload,
        headers=headers,
    )

    assert save_response.status_code == 200
    assert save_response.json() == payload

    get_response = await client.get(
        "/api/v1/users/me/eq",
        headers=headers,
    )

    assert get_response.status_code == 200
    assert get_response.json() == payload


@pytest.mark.anyio
async def test_eq_invalid_band_count(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700003)
    headers = await auth_headers(
        client, user["id"]
    )

    response = await client.put(
        "/api/v1/users/me/eq",
        json={
            "preset": "Flat",
            "bands": [0, 0, 0],
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_eq_invalid_band_range(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700004)
    headers = await auth_headers(
        client, user["id"]
    )

    response = await client.put(
        "/api/v1/users/me/eq",
        json={
            "preset": "Flat",
            "bands": [0, 0, 0, 0, 0, 0, 0, 20],
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_eq_preset_too_long(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 700005)
    headers = await auth_headers(
        client, user["id"]
    )

    response = await client.put(
        "/api/v1/users/me/eq",
        json={
            "preset": "x" * 60,
            "bands": [0, 0, 0, 0, 0, 0, 0, 0],
        },
        headers=headers,
    )

    assert response.status_code == 422
