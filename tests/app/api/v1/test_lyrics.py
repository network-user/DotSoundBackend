import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_set_and_get_lyrics(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 100001)
    track = await create_test_track(
        client, "Lyric Track",
        uploader_id=user["id"],
    )
    headers = await auth_headers(client, user["id"])

    r_set = await client.post(
        f"/api/v1/tracks/{track['id']}/lyrics",
        json={"plain_text": "Hello world lyrics"},
        headers=headers,
    )
    assert r_set.status_code == 200
    assert (
        r_set.json()["plain_text"]
        == "Hello world lyrics"
    )

    r_get = await client.get(
        f"/api/v1/tracks/{track['id']}/lyrics",
    )
    assert r_get.status_code == 200
    assert (
        r_get.json()["plain_text"]
        == "Hello world lyrics"
    )


async def test_get_lyrics_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/lyrics",
    )
    assert r.status_code == 404


async def test_delete_lyrics(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 100002)
    track = await create_test_track(
        client, "Del Lyric Track",
        uploader_id=user["id"],
    )
    headers = await auth_headers(client, user["id"])

    await client.post(
        f"/api/v1/tracks/{track['id']}/lyrics",
        json={"plain_text": "Temporary lyrics"},
        headers=headers,
    )

    r_del = await client.delete(
        f"/api/v1/tracks/{track['id']}/lyrics",
        headers=headers,
    )
    assert r_del.status_code == 204

    r_get = await client.get(
        f"/api/v1/tracks/{track['id']}/lyrics",
    )
    assert r_get.status_code == 404


async def test_set_lyrics_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/api/v1/tracks/1/lyrics",
        json={"plain_text": "No auth"},
    )
    assert r.status_code == 401


async def test_lyrics_translation_crud(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 100003)
    track = await create_test_track(
        client, "Lyric Tr", uploader_id=user["id"]
    )
    headers = await auth_headers(client, user["id"])
    await client.post(
        f"/api/v1/tracks/{track['id']}/lyrics",
        json={"plain_text": "Hello world lyrics"},
        headers=headers,
    )
    put_r = await client.put(
        f"/api/v1/tracks/{track['id']}/lyrics/translations/en",
        json={"translated_text": "Hello world"},
        headers=headers,
    )
    assert put_r.status_code == 200
    assert put_r.json()["language_code"] == "en"

    get_r = await client.get(
        f"/api/v1/tracks/{track['id']}/lyrics",
    )
    assert get_r.status_code == 200
    assert get_r.json()["translations"][0]["language_code"] == "en"

    list_r = await client.get(
        f"/api/v1/tracks/{track['id']}/lyrics/translations",
    )
    assert list_r.status_code == 200
    assert len(list_r.json()) == 1

    del_r = await client.delete(
        f"/api/v1/tracks/{track['id']}/lyrics/translations/en",
        headers=headers,
    )
    assert del_r.status_code == 204


async def test_lyrics_translation_requires_owner(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(client, 100004)
    alien = await create_test_user(client, 100005)
    track = await create_test_track(
        client, "Lyric Tr 2", uploader_id=owner["id"]
    )
    owner_headers = await auth_headers(client, owner["id"])
    alien_headers = await auth_headers(client, alien["id"])
    await client.post(
        f"/api/v1/tracks/{track['id']}/lyrics",
        json={"plain_text": "Lyrics"},
        headers=owner_headers,
    )

    put_r = await client.put(
        f"/api/v1/tracks/{track['id']}/lyrics/translations/en",
        json={"translated_text": "No access"},
        headers=alien_headers,
    )
    assert put_r.status_code == 403
