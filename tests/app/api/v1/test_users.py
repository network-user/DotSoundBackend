from datetime import UTC, datetime, timedelta
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


async def test_listen_history_cursor_pages_unique_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.models.listen_event import ListenEvent

    tg = 7521
    user = await create_test_user(client, tg)
    headers = await auth_headers(client, tg)
    uid = int(user["id"])
    tracks = [TrackFactory.create() for _ in range(3)]
    db_session.add_all(tracks)
    await db_session.flush()
    base = datetime(2026, 5, 2, 14, 30, tzinfo=UTC)
    for idx, track in enumerate(tracks):
        ts = base - timedelta(minutes=idx)
        db_session.add(
            ListenEvent(
                user_id=uid,
                track_id=track.id,
                started_at=ts,
                created_at=ts,
                duration_listened_seconds=60 + idx,
                completed=True,
                skipped=False,
            ),
        )
    db_session.add(
        ListenEvent(
            user_id=uid,
            track_id=tracks[0].id,
            started_at=base - timedelta(hours=1),
            created_at=base - timedelta(hours=1),
            duration_listened_seconds=5,
            completed=False,
            skipped=True,
        ),
    )
    await db_session.commit()

    r_first = await client.get(
        "/api/v1/users/me/listen-history?size=2",
        headers=headers,
    )
    assert r_first.status_code == 200
    first = r_first.json()
    assert [item["id"] for item in first["items"]] == [
        tracks[0].id,
        tracks[1].id,
    ]
    assert first["total"] == 3
    assert first["has_more"] is True
    assert first["next_cursor"] is not None

    r_next = await client.get(
        (
            "/api/v1/users/me/listen-history?size=2"
            f"&cursor={first['next_cursor']}"
        ),
        headers=headers,
    )
    assert r_next.status_code == 200
    page = r_next.json()
    assert [item["id"] for item in page["items"]] == [tracks[2].id]
    assert page["has_more"] is False


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


async def test_get_user_includes_profile_access_fields(
    client: AsyncClient,
) -> None:
    created = await create_test_user(
        client, 88001, username="pubpa"
    )
    uid = int(created["id"])
    r = await client.get(f"/api/v1/users/{uid}")
    assert r.status_code == 200
    body = r.json()
    assert body["profile_access"] == "full"
    assert body["profile_visibility"] == "public"


async def test_hidden_profile_stats_blocked_for_others(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(
        client, 88002, username="hidu2"
    )
    oid = int(owner["id"])
    h = await auth_headers(client, 88002)
    patch = await client.patch(
        "/api/v1/users/me",
        headers=h,
        json={"profile_visibility": "hidden"},
    )
    assert patch.status_code == 200
    stats_other = await client.get(
        f"/api/v1/users/{oid}/stats",
    )
    assert stats_other.status_code == 403
    prof = await client.get(f"/api/v1/users/{oid}")
    assert prof.status_code == 200
    assert prof.json()["profile_access"] == "limited"
    stats_own = await client.get(
        f"/api/v1/users/{oid}/stats",
        headers=h,
    )
    assert stats_own.status_code == 200


@patch("app.api.v1.users.settings")
async def test_user_share_card_profile_url_uses_mini_app_path(
    mock_settings: object,
    client: AsyncClient,
) -> None:
    created = await create_test_user(
        client, 88055, username="shareu55"
    )
    uid = int(created["id"])
    mock_settings.mini_app_url = "https://dotsound.example"
    r = await client.get(f"/api/v1/users/{uid}/share-card")
    assert r.status_code == 200
    body = r.json()
    assert body["profile_url"] == (
        f"https://dotsound.example/mini_app/profile/{uid}"
    )
    assert body["deep_link"] is None or "t.me" in body["deep_link"]


async def test_hidden_profile_share_card_ok_for_owner(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(
        client, 88066, username="hidshare"
    )
    oid = int(owner["id"])
    headers = await auth_headers(client, 88066)
    patch = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"profile_visibility": "hidden"},
    )
    assert patch.status_code == 200
    own_card = await client.get(
        f"/api/v1/users/{oid}/share-card",
        headers=headers,
    )
    assert own_card.status_code == 200
    assert "/profile/" in own_card.json()["profile_url"]
    await create_test_user(client, 88067, username="stranger")
    stranger = await client.get(f"/api/v1/users/{oid}/share-card")
    assert stranger.status_code == 403


async def test_followers_only_profile_stats_after_follow(
    client: AsyncClient,
) -> None:
    a = await create_test_user(client, 88033, username="ownf33")
    await create_test_user(client, 88044, username="visf44")
    aid = int(a["id"])
    ha = await auth_headers(client, 88033)
    hb = await auth_headers(client, 88044)
    pa = await client.patch(
        "/api/v1/users/me",
        headers=ha,
        json={"profile_visibility": "followers_only"},
    )
    assert pa.status_code == 200
    denied = await client.get(
        f"/api/v1/users/{aid}/stats",
        headers=hb,
    )
    assert denied.status_code == 403
    fo = await client.post(
        f"/api/v1/users/{aid}/follow",
        headers=hb,
    )
    assert fo.status_code == 200
    ok = await client.get(
        f"/api/v1/users/{aid}/stats",
        headers=hb,
    )
    assert ok.status_code == 200
