import pytest
from dirty_equals import IsPartialDict
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_create_and_get_playlist(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20001)
    headers = await auth_headers(client, owner["id"])

    r = await client.post(
        "/api/v1/playlists",
        json={
            "name": "My Mix",
            "is_public": True,
        },
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Mix"
    playlist_id = data["id"]

    r2 = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json() == IsPartialDict(
        name="My Mix",
        tracks=[],
    )


async def test_add_and_remove_track(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await create_test_user(client, 20002)
    track = await create_test_track(client, "pl_track", owner["id"])
    await db_session.execute(
        update(Track)
        .where(Track.id == track["id"])
        .values(file_key="test/pl_track_mux.mp3")
    )
    await db_session.commit()
    headers = await auth_headers(client, owner["id"])

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Mix"},
        headers=headers,
    )
    playlist_id = pl.json()["id"]

    r_add = await client.post(
        f"/api/v1/playlists/{playlist_id}/tracks",
        json={
            "track_id": track["id"],
            "position": 0,
        },
        headers=headers,
    )
    assert r_add.status_code == 204

    r_get = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert len(r_get.json()["tracks"]) == 1

    r_rm = await client.delete(
        f"/api/v1/playlists/{playlist_id}" f"/tracks/{track['id']}",
        headers=headers,
    )
    assert r_rm.status_code == 204

    r_get2 = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r_get2.json()["tracks"] == []


async def test_get_playlist_tracks_page(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await create_test_user(client, 20012)
    headers = await auth_headers(client, owner["id"])
    tracks = [
        await create_test_track(client, f"pl_page_{idx}", owner["id"])
        for idx in range(3)
    ]
    for track in tracks:
        await db_session.execute(
            update(Track)
            .where(Track.id == track["id"])
            .values(file_key=f"test/pl_page_{track['id']}.mp3")
        )
    await db_session.commit()

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Paged"},
        headers=headers,
    )
    playlist_id = pl.json()["id"]
    for position, track in enumerate(tracks):
        r_add = await client.post(
            f"/api/v1/playlists/{playlist_id}/tracks",
            json={
                "track_id": track["id"],
                "position": position,
            },
            headers=headers,
        )
        assert r_add.status_code == 204

    r_page1 = await client.get(
        f"/api/v1/playlists/{playlist_id}?tracks_page=1&tracks_size=2",
        headers=headers,
    )
    assert r_page1.status_code == 200
    body1 = r_page1.json()
    assert [item["id"] for item in body1["tracks"]] == [
        tracks[0]["id"],
        tracks[1]["id"],
    ]
    assert body1["tracks_total"] == 3
    assert body1["tracks_page"] == 1
    assert body1["tracks_size"] == 2
    assert body1["tracks_has_more"] is True
    assert body1["tracks_next_cursor"] is not None

    r_cursor = await client.get(
        (
            f"/api/v1/playlists/{playlist_id}"
            f"?tracks_size=2&tracks_cursor={body1['tracks_next_cursor']}"
        ),
        headers=headers,
    )
    assert r_cursor.status_code == 200
    cursor_body = r_cursor.json()
    assert [item["id"] for item in cursor_body["tracks"]] == [
        tracks[2]["id"],
    ]
    assert cursor_body["tracks_total"] == 3
    assert cursor_body["tracks_has_more"] is False

    r_page2 = await client.get(
        f"/api/v1/playlists/{playlist_id}?tracks_page=2&tracks_size=2",
        headers=headers,
    )
    assert r_page2.status_code == 200
    body2 = r_page2.json()
    assert [item["id"] for item in body2["tracks"]] == [tracks[2]["id"]]
    assert body2["tracks_total"] == 3
    assert body2["tracks_has_more"] is False


async def test_list_playlists_cursor_response(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20013)
    headers = await auth_headers(client, owner["id"])
    first = await client.post(
        "/api/v1/playlists",
        json={"name": "First"},
        headers=headers,
    )
    second = await client.post(
        "/api/v1/playlists",
        json={"name": "Second"},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201

    r_first_page = await client.get(
        "/api/v1/playlists?size=1",
        headers=headers,
    )
    assert r_first_page.status_code == 200
    first_page = r_first_page.json()
    assert [item["name"] for item in first_page["items"]] == ["Second"]
    assert first_page["total"] == 2
    assert first_page["has_more"] is True
    assert first_page["next_cursor"] is not None

    r_next_page = await client.get(
        f"/api/v1/playlists?size=1&cursor={first_page['next_cursor']}",
        headers=headers,
    )
    assert r_next_page.status_code == 200
    next_page = r_next_page.json()
    assert [item["name"] for item in next_page["items"]] == ["First"]
    assert next_page["total"] == 2
    assert next_page["has_more"] is False


async def test_delete_playlist(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20003)
    headers = await auth_headers(client, owner["id"])

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Temp"},
        headers=headers,
    )
    playlist_id = pl.json()["id"]

    r = await client.delete(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r.status_code == 204

    r2 = await client.get(
        f"/api/v1/playlists/{playlist_id}",
        headers=headers,
    )
    assert r2.status_code == 404


async def test_forbidden_update(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 20004)
    other = await create_test_user(client, 20005)
    owner_headers = await auth_headers(client, owner["id"])
    other_headers = await auth_headers(client, other["id"])

    pl = await client.post(
        "/api/v1/playlists",
        json={"name": "Private"},
        headers=owner_headers,
    )
    playlist_id = pl.json()["id"]

    r = await client.put(
        f"/api/v1/playlists/{playlist_id}",
        json={"name": "Hacked"},
        headers=other_headers,
    )
    assert r.status_code == 403
