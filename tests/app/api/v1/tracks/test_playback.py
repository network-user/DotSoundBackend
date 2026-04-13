from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_stream_track_not_found(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/tracks/99999/stream"
    )
    assert response.status_code == 404


async def test_stream_no_file_key_returns_422(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50001)
    track = await create_test_track(
        client, "StreamMe", user["id"]
    )
    track_id = track["id"]

    response = await client.get(
        f"/api/v1/tracks/{track_id}/stream"
    )
    assert response.status_code == 422


async def test_play_increments_count(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50002)
    track = await create_test_track(
        client, "PlayMe", user["id"]
    )
    track_id = track["id"]

    r1 = await client.post(
        f"/api/v1/tracks/{track_id}/play"
    )
    assert r1.status_code == 200
    assert r1.json()["play_count"] >= 0

    r2 = await client.post(
        f"/api/v1/tracks/{track_id}/play"
    )
    assert r2.status_code == 200


async def test_play_not_found(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/tracks/99999/play"
    )
    assert response.status_code == 404


async def test_get_track_by_id(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50010)
    track = await create_test_track(
        client, "GetMe", user["id"]
    )
    track_id = track["id"]

    r = await client.get(
        f"/api/v1/tracks/{track_id}"
    )
    assert r.status_code == 200
    assert r.json()["title"] == "GetMe"


async def test_get_track_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/99999")
    assert r.status_code == 404


async def test_get_cover_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/cover"
    )
    assert r.status_code == 404


async def test_get_cover_no_cover_key(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50011)
    track = await create_test_track(
        client, "NoCover", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{track['id']}/cover"
    )
    assert r.status_code == 404


async def test_adjacent_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/adjacent"
    )
    assert r.status_code == 404


async def test_adjacent_sequential(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50012)
    t1 = await create_test_track(
        client, "Adj1", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t1['id']}/adjacent"
        f"?mode=sequential"
    )
    assert r.status_code == 200
    data = r.json()
    assert "prev_id" in data
    assert "next_id" in data


async def test_adjacent_repeat_one(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50013)
    t = await create_test_track(
        client, "Repeat", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/adjacent"
        f"?mode=repeat_one"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["prev_id"] == t["id"]
    assert data["next_id"] == t["id"]


async def test_adjacent_shuffle(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50014)
    t = await create_test_track(
        client, "Shuffle", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/adjacent"
        f"?mode=shuffle"
    )
    assert r.status_code == 200


async def test_get_track_card(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50015)
    t = await create_test_track(
        client, "Card", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/card"
    )
    assert r.status_code == 200
    assert "title" in r.json()


async def test_get_track_card_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/card"
    )
    assert r.status_code == 404


async def test_get_share_links(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50016)
    t = await create_test_track(
        client, "Share", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/share"
    )
    assert r.status_code == 200
    data = r.json()
    assert "url" in data
    assert "telegram_share_url" in data


async def test_get_share_links_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/share"
    )
    assert r.status_code == 404


async def test_video_proxy_success(
    client: AsyncClient,
) -> None:
    from io import BytesIO

    user = await create_test_user(client, 50020)
    headers = await auth_headers(
        client, user["id"]
    )
    t = await create_test_track(
        client, "VidProxy", user["id"]
    )

    video_bytes = b"\x00\x00\x00\x1cftypisom" + (
        b"\x00" * 100
    )
    with patch(
        "app.core.s3.upload_object",
        new_callable=AsyncMock,
    ):
        await client.post(
            f"/api/v1/tracks/{t['id']}/video",
            headers=headers,
            files={
                "video": (
                    "clip.mp4",
                    BytesIO(video_bytes),
                    "video/mp4",
                )
            },
        )

    with patch(
        "app.core.s3.download_object",
        new_callable=AsyncMock,
        return_value=video_bytes,
    ):
        r = await client.get(
            f"/api/v1/tracks/{t['id']}/video"
        )
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert (
        r.headers["cache-control"]
        == "public, max-age=3600"
    )


async def test_video_proxy_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/video"
    )
    assert r.status_code == 404


async def test_video_proxy_no_video_key(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50017)
    t = await create_test_track(
        client, "NoVid", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/video"
    )
    assert r.status_code == 404


async def test_audio_stream_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/audio"
    )
    assert r.status_code == 404


async def test_audio_stream_no_file_key(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50018)
    t = await create_test_track(
        client, "NoAudio", user["id"]
    )

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/audio"
    )
    assert r.status_code == 422
