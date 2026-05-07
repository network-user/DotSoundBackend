from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, create_test_user
from tests.factories import TrackFactory

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
    assert response.json() == IsPartialDict(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        is_active=True,
    )


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


async def test_listen_history_includes_last_listen_meta(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.models.listen_event import ListenEvent

    tg = 7520
    user = await create_test_user(client, tg)
    headers = await auth_headers(client, tg)
    uid = int(user["id"])
    track = TrackFactory.create()
    db_session.add(track)
    await db_session.flush()
    ts = datetime(2026, 5, 1, 14, 30, tzinfo=UTC)
    db_session.add(
        ListenEvent(
            user_id=uid,
            track_id=track.id,
            started_at=ts,
            created_at=ts,
            duration_listened_seconds=125,
            completed=True,
            skipped=False,
        ),
    )
    await db_session.commit()
    res = await client.get(
        "/api/v1/users/me/listen-history?limit=10",
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.json()
    rows = payload["items"]
    assert rows
    item = next(r for r in rows if r["id"] == track.id)
    assert item["last_listen_at"] is not None
    assert item["last_listen_seconds"] == 125


@patch("app.api.v1.users.settings")
async def test_debug_reset_onboarding_404_when_not_debug(
    mock_settings: object,
    client: AsyncClient,
) -> None:
    mock_settings.debug = False
    await create_test_user(client, 9001)
    headers = await auth_headers(client, 9001)
    r = await client.post(
        "/api/v1/users/me/debug/reset-onboarding",
        headers=headers,
    )
    assert r.status_code == 404
