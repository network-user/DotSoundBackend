"""Integration tests for /artists/me — the user's own artist profile."""

from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def _user_with_name(
    client: AsyncClient,
    tg_id: int,
    display: str,
) -> dict[str, str]:
    await create_test_user(client, tg_id, first_name="X")
    headers = await auth_headers(client, tg_id)
    r = await client.patch(
        "/api/v1/users/me",
        json={"display_name": display},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return headers


async def test_get_me_returns_no_artist_initially(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10001, "Alice")
    r = await client.get("/api/v1/artists/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["has_artist"] is False
    assert body["display_name"] == "Alice"
    assert body["artist"] is None


async def test_ensure_creates_artist(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10002, "Bob")
    r = await client.post(
        "/api/v1/artists/me/ensure", headers=headers
    )
    assert r.status_code == 201, r.text
    a = r.json()["artist"]
    assert a["name"] == "Bob"
    assert a["bio"] is None

    follow = await client.get(
        "/api/v1/artists/me", headers=headers
    )
    body = follow.json()
    assert body["has_artist"] is True
    assert body["artist"]["id"] == a["id"]


async def test_ensure_400_when_display_empty(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 10003, first_name="C")
    headers = await auth_headers(client, 10003)
    # No display_name set -> 400
    r = await client.post(
        "/api/v1/artists/me/ensure", headers=headers
    )
    assert r.status_code == 400


async def test_patch_updates_fields(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10004, "Carol")
    await client.post("/api/v1/artists/me/ensure", headers=headers)
    r = await client.patch(
        "/api/v1/artists/me",
        json={
            "bio": "indie producer",
            "country": "ru",
            "birthplace": "Moscow",
            "website_url": "https://example.com",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["bio"] == "indie producer"
    assert a["country"] == "RU"  # upper-cased
    assert a["birthplace"] == "Moscow"
    assert a["website_url"].startswith("https://example.com")


async def test_patch_rejects_invalid_country(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10005, "Dan")
    await client.post("/api/v1/artists/me/ensure", headers=headers)
    r = await client.patch(
        "/api/v1/artists/me",
        json={"country": "XX"},
        headers=headers,
    )
    assert r.status_code == 422


async def test_patch_rejects_non_http_url(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10006, "Eva")
    await client.post("/api/v1/artists/me/ensure", headers=headers)
    r = await client.patch(
        "/api/v1/artists/me",
        json={"website_url": "ftp://example.com"},
        headers=headers,
    )
    assert r.status_code == 422


async def test_patch_404_when_no_artist(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10007, "Frank")
    r = await client.patch(
        "/api/v1/artists/me",
        json={"bio": "hello"},
        headers=headers,
    )
    assert r.status_code == 404


async def test_avatar_upload_and_remove(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10008, "Gina")
    await client.post("/api/v1/artists/me/ensure", headers=headers)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + b"\x00\x00\x00\x01\x00\x00\x00\x01"
        + b"\x08\x06\x00\x00\x00"
        + b"\x1f\x15\xc4\x89"
        + b"\x00\x00\x00\rIDAT"
        + b"x\x9cc\x00\x01\x00\x00\x05\x00\x01"
        + b"\x0d\n-\xb4"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    with patch(
        "app.core.s3.upload_image",
        new_callable=AsyncMock,
        return_value=(
            "artist-avatars/x/abcd.webp",
            "artist-avatars/x/abcd_thumb.webp",
            64,
            64,
        ),
    ):
        r = await client.post(
            "/api/v1/artists/me/avatar",
            headers=headers,
            files={
                "avatar": (
                    "a.png",
                    BytesIO(png),
                    "image/png",
                )
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["image_key"] == "artist-avatars/x/abcd.webp"

    r2 = await client.delete(
        "/api/v1/artists/me/avatar", headers=headers
    )
    assert r2.status_code == 200
    assert r2.json()["image_key"] is None


async def test_avatar_rejects_bad_mime(
    client: AsyncClient,
) -> None:
    headers = await _user_with_name(client, 10009, "Henry")
    await client.post("/api/v1/artists/me/ensure", headers=headers)
    r = await client.post(
        "/api/v1/artists/me/avatar",
        headers=headers,
        files={
            "avatar": (
                "a.gif",
                BytesIO(b"GIF89a..."),
                "image/gif",
            )
        },
    )
    assert r.status_code == 415


async def test_cross_user_isolation(
    client: AsyncClient,
) -> None:
    a_headers = await _user_with_name(client, 10010, "Ivan")
    b_headers = await _user_with_name(client, 10011, "Julia")
    await client.post(
        "/api/v1/artists/me/ensure", headers=a_headers
    )
    await client.patch(
        "/api/v1/artists/me",
        json={"bio": "ivan-only"},
        headers=a_headers,
    )
    # B has no artist; PATCH should 404, GET should report has_artist=False.
    r = await client.get("/api/v1/artists/me", headers=b_headers)
    body = r.json()
    assert body["has_artist"] is False
    p = await client.patch(
        "/api/v1/artists/me",
        json={"bio": "stealth"},
        headers=b_headers,
    )
    assert p.status_code == 404
