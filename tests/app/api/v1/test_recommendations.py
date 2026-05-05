import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_home_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/home"
    )
    assert r.status_code == 401


async def test_home_empty(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7001)
    headers = await auth_headers(client, 7001)

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "sections" in data
    assert "highlights" in data
    assert "maturity" in data


async def test_home_highlights_populated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Setup: create some tracks and listens to trigger highlights
    user_id = 7003
    await create_test_user(client, user_id)
    headers = await auth_headers(client, user_id)

    # Create a track
    from tests.factories import TrackFactory
    track = TrackFactory.create()
    db_session.add(track)
    await db_session.commit()

    # Create an incomplete listen event for this track
    from app.models.listen_event import ListenEvent
    from datetime import datetime, UTC
    listen = ListenEvent(
        user_id=1,  # Fixed ID for the first user in tests
        track_id=track.id,
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        duration_listened_seconds=10,
        completed=False,
        skipped=False,
    )
    db_session.add(listen)
    await db_session.commit()

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["highlights"]) > 0
    assert data["highlights"][0]["track"]["id"] == track.id
    assert data["highlights"][0]["label"] == "Продолжить"


async def test_home_returns_sections(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7002)
    headers = await auth_headers(client, 7002)

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["sections"], list)
    assert data["maturity"] in [
        "cold",
        "warm",
        "calibrated",
        "enriched",
        "personalized",
    ]


async def test_similar_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/similar/99999"
    )
    assert r.status_code == 200
    assert r.json()["tracks"] == []


async def test_daily_mix(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7004)
    headers = await auth_headers(client, 7004)

    r = await client.get(
        "/api/v1/recommendations/daily-mix",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data


async def test_user_choice_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/user-choice"
    )
    assert r.status_code == 401


async def test_user_choice_ok(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7006)
    headers = await auth_headers(client, 7006)
    r = await client.get(
        "/api/v1/recommendations/user-choice?limit=10",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data
    assert "score_version" in data
    assert isinstance(
        data["tracks"],
        list,
    )


async def test_radio_missing_seed(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7005)
    headers = await auth_headers(client, 7005)

    r = await client.get(
        "/api/v1/recommendations/radio",
        headers=headers,
    )
    assert r.status_code == 422
