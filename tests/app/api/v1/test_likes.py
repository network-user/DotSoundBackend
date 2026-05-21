from datetime import UTC, datetime, timedelta

import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.like import Like
from app.models.track import Track
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
    assert r.json()["has_more"] is False


async def test_get_user_likes_pagination(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10005)
    headers = await auth_headers(
        client, user["id"]
    )
    tracks = []
    for i in range(3):
        t = await create_test_track(
            client, f"PagLike{i}", user["id"]
        )
        tracks.append(t)
        await client.post(
            f"/api/v1/likes/{user['id']}"
            f"/{t['id']}",
            headers=headers,
        )

    r1 = await client.get(
        f"/api/v1/likes/{user['id']}"
        f"?page=1&size=2"
    )
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["total"] == 3
    assert len(data1["items"]) == 2
    assert data1["page"] == 1
    assert data1["has_more"] is True

    r2 = await client.get(
        f"/api/v1/likes/{user['id']}"
        f"?page=2&size=2"
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2["items"]) == 1
    assert data2["page"] == 2
    assert data2["has_more"] is False


async def test_liked_tracks_includes_liked_at(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 10006)
    track = await create_test_track(
        client, "LikedAtTrack", user["id"]
    )
    headers = await auth_headers(client, user["id"])
    await client.post(
        f"/api/v1/likes/{user['id']}/{track['id']}",
        headers=headers,
    )
    r = await client.get(f"/api/v1/likes/{user['id']}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert "liked_at" in items[0]
    assert items[0]["liked_at"] is not None


async def test_liked_tracks_sort_oldest_before_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 100061)
    headers = await auth_headers(client, user["id"])
    tracks = [
        await create_test_track(client, f"OldestSort{i}", user["id"])
        for i in range(3)
    ]
    for track in tracks:
        await client.post(
            f"/api/v1/likes/{user['id']}/{track['id']}",
            headers=headers,
        )

    base = datetime(2026, 1, 1, tzinfo=UTC)
    liked_at_by_track = {
        tracks[0]["id"]: base + timedelta(minutes=2),
        tracks[1]["id"]: base,
        tracks[2]["id"]: base + timedelta(minutes=1),
    }
    for track_id, liked_at in liked_at_by_track.items():
        await db_session.execute(
            update(Like)
            .where(
                Like.user_id == user["id"],
                Like.track_id == track_id,
            )
            .values(created_at=liked_at)
        )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/likes/{user['id']}?page=1&size=1&sort=oldest"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert [item["id"] for item in data["items"]] == [
        tracks[1]["id"]
    ]


async def test_liked_tracks_sort_artist_before_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 100062)
    headers = await auth_headers(client, user["id"])
    tracks = [
        await create_test_track(client, "Gamma Title", user["id"]),
        await create_test_track(client, "Alpha Title", user["id"]),
        await create_test_track(client, "Beta Title", user["id"]),
    ]
    artist_by_track = {
        tracks[0]["id"]: "Zed Artist",
        tracks[1]["id"]: "Alpha Artist",
        tracks[2]["id"]: "Middle Artist",
    }
    for track in tracks:
        await client.post(
            f"/api/v1/likes/{user['id']}/{track['id']}",
            headers=headers,
        )
    for track_id, artist in artist_by_track.items():
        await db_session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(artist=artist)
        )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/likes/{user['id']}?page=1&size=1&sort=artist"
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        tracks[1]["id"]
    ]


async def test_liked_queue_shuffle_uses_tracks_beyond_first_page(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 100063)
    headers = await auth_headers(client, user["id"])
    tracks = []
    for i in range(25):
        track = await create_test_track(
            client, f"QueueShuffle{i}", user["id"]
        )
        tracks.append(track)
        await client.post(
            f"/api/v1/likes/{user['id']}/{track['id']}",
            headers=headers,
        )

    current_id = tracks[0]["id"]
    response = await client.get(
        f"/api/v1/likes/{user['id']}/queue"
        f"?current_track_id={current_id}&size=100&shuffle=true"
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["next_tracks"]}
    expected = {track["id"] for track in tracks if track["id"] != current_id}
    assert ids == expected


async def _insert_sc_track(
    db_session: AsyncSession,
    title: str,
    uploader_id: int,
) -> int:
    track = Track(
        title=title,
        artist="SC Artist",
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        play_count=0,
        is_active=True,
        is_public=True,
        uploaded_by_id=uploader_id,
        sc_url=f"https://soundcloud.com/test/{title}",
        duration_seconds=180,
    )
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return int(track.id)


async def test_liked_tracks_source_filter_platform(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 10007)
    headers = await auth_headers(client, user["id"])
    ugc_track = await create_test_track(
        client, "PlatformTrack", user["id"]
    )
    sc_id = await _insert_sc_track(
        db_session, "ScFilterTrack1", user["id"]
    )
    for tid in (ugc_track["id"], sc_id):
        await client.post(
            f"/api/v1/likes/{user['id']}/{tid}",
            headers=headers,
        )

    r = await client.get(
        f"/api/v1/likes/{user['id']}?source=platform"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    ids = [it["id"] for it in data["items"]]
    assert ugc_track["id"] in ids
    assert sc_id not in ids


async def test_liked_tracks_source_filter_soundcloud(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 10008)
    headers = await auth_headers(client, user["id"])
    ugc_track = await create_test_track(
        client, "UgcForScFilter", user["id"]
    )
    sc_id = await _insert_sc_track(
        db_session, "ScFilterTrack2", user["id"]
    )
    for tid in (ugc_track["id"], sc_id):
        await client.post(
            f"/api/v1/likes/{user['id']}/{tid}",
            headers=headers,
        )

    r = await client.get(
        f"/api/v1/likes/{user['id']}?source=soundcloud"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    ids = [it["id"] for it in data["items"]]
    assert sc_id in ids
    assert ugc_track["id"] not in ids


async def test_liked_tracks_source_filter_other(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 10009)
    headers = await auth_headers(client, user["id"])
    ugc_track = await create_test_track(
        client, "UgcForOtherFilter", user["id"]
    )
    sc_id = await _insert_sc_track(
        db_session, "ScFilterTrack3", user["id"]
    )
    other_track = Track(
        title="BandcampTrack",
        artist="BC Artist",
        source="bandcamp",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        play_count=0,
        is_active=True,
        is_public=True,
        uploaded_by_id=user["id"],
        duration_seconds=200,
    )
    db_session.add(other_track)
    await db_session.commit()
    await db_session.refresh(other_track)
    other_id = int(other_track.id)

    for tid in (ugc_track["id"], sc_id, other_id):
        await client.post(
            f"/api/v1/likes/{user['id']}/{tid}",
            headers=headers,
        )

    r = await client.get(
        f"/api/v1/likes/{user['id']}?source=other"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    ids = [it["id"] for it in data["items"]]
    assert other_id in ids
    assert ugc_track["id"] not in ids
    assert sc_id not in ids
