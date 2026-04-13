from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_upload_valid_mp3(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60001)
    track = await create_test_track(
        client, "Test Track", user["id"]
    )
    assert track["title"] == "Test Track"
    assert "file_key" in track


async def test_upload_invalid_mime(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60002)
    headers = await auth_headers(
        client, user["id"]
    )
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "Bad File"},
        files={
            "file": (
                "image.png",
                BytesIO(b"\x89PNG"),
                "image/png",
            )
        },
        headers=headers,
    )
    assert response.status_code == 415


async def test_upload_too_large(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60003)
    headers = await auth_headers(
        client, user["id"]
    )
    big_data = (
        b"\xff\xfb"
        + b"\x00" * (101 * 1024 * 1024)
    )
    response = await client.post(
        "/api/v1/tracks/upload",
        data={"title": "Huge"},
        files={
            "file": (
                "big.mp3",
                BytesIO(big_data),
                "audio/mpeg",
            )
        },
        headers=headers,
    )
    assert response.status_code == 413


async def test_upload_no_artist(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60004)
    track = await create_test_track(
        client, "No Artist", user["id"]
    )
    assert track["title"] == "No Artist"


async def test_list_my_tracks(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60010)
    headers = await auth_headers(
        client, user["id"]
    )
    await create_test_track(
        client, "MyTrack1", user["id"]
    )
    await create_test_track(
        client, "MyTrack2", user["id"]
    )

    r = await client.get(
        "/api/v1/tracks/my", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


async def test_list_my_tracks_unauthorized(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/my")
    assert r.status_code in (401, 403)


async def test_delete_track(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60011)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "ToDelete", user["id"]
    )

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ):
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}",
            headers=headers,
        )
    assert r.status_code == 204


async def test_delete_track_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60012)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.delete(
        "/api/v1/tracks/99999", headers=headers
    )
    assert r.status_code == 404


async def test_update_track_visibility(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60013)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VisTrack", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={"is_public": False},
    )
    assert r.status_code == 200
    assert r.json()["is_public"] is False


async def test_update_track_no_fields(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60014)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "NoField", user["id"]
    )

    r = await client.patch(
        f"/api/v1/tracks/{track['id']}",
        headers=headers,
        json={},
    )
    assert r.status_code == 400


async def test_update_track_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60015)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.patch(
        "/api/v1/tracks/99999",
        headers=headers,
        json={"is_public": False},
    )
    assert r.status_code == 404


async def test_upload_cover_unsupported_mime(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60016)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "CoverTrack", user["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{track['id']}/cover",
        headers=headers,
        files={
            "cover": (
                "image.bmp",
                BytesIO(b"BM" + b"\x00" * 50),
                "image/bmp",
            )
        },
    )
    assert r.status_code == 415


async def test_upload_video_unsupported_mime(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60017)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidTrack", user["id"]
    )

    r = await client.post(
        f"/api/v1/tracks/{track['id']}/video",
        headers=headers,
        files={
            "video": (
                "vid.avi",
                BytesIO(b"\x00" * 100),
                "video/avi",
            )
        },
    )
    assert r.status_code == 415


async def test_delete_video_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60018)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.delete(
        "/api/v1/tracks/99999/video",
        headers=headers,
    )
    assert r.status_code == 404


async def test_regenerate_cover_not_found(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60019)
    headers = await auth_headers(
        client, user["id"]
    )

    r = await client.post(
        "/api/v1/tracks/99999/cover/generate",
        headers=headers,
    )
    assert r.status_code == 404


async def test_upload_video_success(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60020)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidOK", user["id"]
    )

    video_data = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with patch(
        "app.core.s3.upload_object",
        new_callable=AsyncMock,
    ):
        r = await client.post(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_data),
                    "video/mp4",
                )
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["video_key"] is not None
    assert data["video_key"].startswith("videos/")


async def test_delete_video_success(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60021)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "VidDel", user["id"]
    )

    video_data = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with patch(
        "app.core.s3.upload_object",
        new_callable=AsyncMock,
    ):
        r = await client.post(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_data),
                    "video/mp4",
                )
            },
        )
    assert r.json()["video_key"] is not None

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ) as mock_del:
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
        )
    assert r.status_code == 204
    mock_del.assert_called_once()


async def test_delete_track_cleans_video_s3(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 60022)
    headers = await auth_headers(
        client, user["id"]
    )
    track = await create_test_track(
        client, "CleanVid", user["id"]
    )

    video_data = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with patch(
        "app.core.s3.upload_object",
        new_callable=AsyncMock,
    ):
        await client.post(
            f"/api/v1/tracks/{track['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_data),
                    "video/mp4",
                )
            },
        )

    with patch(
        "app.core.s3.delete_object",
        new_callable=AsyncMock,
    ) as mock_del:
        r = await client.delete(
            f"/api/v1/tracks/{track['id']}",
            headers=headers,
        )
    assert r.status_code == 204
    deleted_keys = [
        c.args[0] for c in mock_del.call_args_list
    ]
    assert any(
        k.startswith("videos/") for k in deleted_keys
    )
