from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
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


async def test_stream_track_not_found(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/tracks/99999/stream")
    assert response.status_code == 404


async def test_stream_no_file_key_returns_422(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50001)
    track = await create_test_track(client, "StreamMe", user["id"])
    track_id = track["id"]

    response = await client.get(f"/api/v1/tracks/{track_id}/stream")
    assert response.status_code == 422


async def test_play_increments_count(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50002)
    track = await create_test_track(client, "PlayMe", user["id"])
    track_id = track["id"]

    r1 = await client.post(f"/api/v1/tracks/{track_id}/play")
    assert r1.status_code == 200
    assert r1.json()["play_count"] >= 0

    r2 = await client.post(f"/api/v1/tracks/{track_id}/play")
    assert r2.status_code == 200


async def test_play_not_found(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/tracks/99999/play")
    assert response.status_code == 404


async def test_get_track_by_id(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50010)
    track = await create_test_track(client, "GetMe", user["id"])
    track_id = track["id"]

    r = await client.get(f"/api/v1/tracks/{track_id}")
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
    r = await client.get("/api/v1/tracks/99999/cover")
    assert r.status_code == 404


async def test_get_cover_no_cover_key(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50011)
    track = await create_test_track(client, "NoCover", user["id"])

    r = await client.get(f"/api/v1/tracks/{track['id']}/cover")
    assert r.status_code == 404


async def test_adjacent_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/99999/adjacent")
    assert r.status_code == 404


async def test_adjacent_sequential(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50012)
    t1 = await create_test_track(client, "Adj1", user["id"])

    r = await client.get(
        f"/api/v1/tracks/{t1['id']}/adjacent" f"?mode=sequential"
    )
    assert r.status_code == 200
    data = r.json()
    assert "prev_id" in data
    assert "next_id" in data


async def test_adjacent_repeat_one(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50013)
    t = await create_test_track(client, "Repeat", user["id"])

    r = await client.get(
        f"/api/v1/tracks/{t['id']}/adjacent" f"?mode=repeat_one"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["prev_id"] == t["id"]
    assert data["next_id"] == t["id"]


async def test_adjacent_shuffle(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50014)
    t = await create_test_track(client, "Shuffle", user["id"])

    r = await client.get(f"/api/v1/tracks/{t['id']}/adjacent" f"?mode=shuffle")
    assert r.status_code == 200


async def test_get_track_card(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50015)
    t = await create_test_track(client, "Card", user["id"])

    r = await client.get(f"/api/v1/tracks/{t['id']}/card")
    assert r.status_code == 200
    assert "title" in r.json()


async def test_get_track_card_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/99999/card")
    assert r.status_code == 404


async def test_get_share_links(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50016)
    t = await create_test_track(client, "Share", user["id"])

    r = await client.get(f"/api/v1/tracks/{t['id']}/share")
    assert r.status_code == 200
    data = r.json()
    assert "url" in data
    assert "telegram_share_url" in data


async def test_get_share_links_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/99999/share")
    assert r.status_code == 404


async def test_video_proxy_success(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from io import BytesIO

    user = await create_test_user(client, 50020)
    headers = await auth_headers(client, user["id"])
    t = await create_test_track(client, "VidProxy", user["id"])

    video_bytes = b"\x00\x00\x00\x1cftypisom" + (b"\x00" * 100)
    with (
        patch(
            "app.core.s3.upload_object",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.file_validator.validate_video",
            return_value="video/mp4",
        ),
        patch(
            "app.services.video_transcoding.transcode_video.kiq",
            new_callable=AsyncMock,
        ),
    ):
        up = await client.post(
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
        assert up.status_code in (200, 201, 204)
    await db_session.execute(
        update(Track)
        .where(Track.id == t["id"])
        .values(video_key="videos/px1.mp4")
    )
    await db_session.commit()

    with patch(
        "app.core.s3.download_object",
        new_callable=AsyncMock,
        return_value=video_bytes,
    ):
        r = await client.get(f"/api/v1/tracks/{t['id']}/video")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert r.headers["cache-control"] == "public, max-age=3600"


async def test_video_proxy_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/99999/video")
    assert r.status_code == 404


async def test_video_proxy_no_video_key(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50017)
    t = await create_test_track(client, "NoVid", user["id"])

    r = await client.get(f"/api/v1/tracks/{t['id']}/video")
    assert r.status_code == 404


async def test_audio_stream_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/tracks/99999/audio")
    assert r.status_code == 404


async def test_audio_stream_no_file_key(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 50018)
    t = await create_test_track(client, "NoAudio", user["id"])

    r = await client.get(f"/api/v1/tracks/{t['id']}/audio")
    assert r.status_code == 422


async def test_audio_stream_force_progressive_skips_hls_redirect(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50021)
    t = await create_test_track(client, "HlsRedirect", user["id"])
    track_id = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(
            hls_manifest_key="hls/1/master.m3u8",
            file_key="anon/playback-hls-test.mp3",
        )
    )
    await db_session.commit()

    r302 = await client.get(f"/api/v1/tracks/{track_id}/audio")
    assert r302.status_code == 302
    assert r302.headers["location"].endswith(
        f"/api/v1/tracks/{track_id}/hls/master.m3u8"
    )

    mp3 = b"\xff\xfb" + b"\x00" * 32
    with patch(
        "app.core.s3.download_object_range",
        new_callable=AsyncMock,
        return_value=(mp3, len(mp3), None, "audio/mpeg"),
    ):
        r = await client.get(
            f"/api/v1/tracks/{track_id}/audio" f"?force_progressive=true"
        )
    assert r.status_code == 200
    assert r.content == mp3
    assert r.headers["content-type"] == "audio/mpeg"


async def test_soundcloud_progressive_stream_returns_same_origin_audio(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50190)
    t = await create_test_track(client, "ThirdSC", user["id"])
    tid = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == tid)
        .values(
            access_mode="third_party_stream",
            source_platform="soundcloud",
            sc_url="https://soundcloud.com/x/y",
            file_key=None,
            hls_manifest_key=None,
        )
    )
    await db_session.commit()

    async def fake_resolve(
        _tr: object,
        _sess: object,
        *,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        return "https://media.sndcdn.com/progressive.mp3", "progressive"

    with patch(
        "app.api.v1.tracks.playback._resolve_third_party_stream",
        new=fake_resolve,
    ):
        r = await client.get(f"/api/v1/tracks/{tid}/stream")
    assert r.status_code == 200
    payload = r.json()
    assert payload["stream_type"] == "direct"
    assert payload["url"].endswith(
        f"/api/v1/tracks/{tid}/audio",
    )


async def test_soundcloud_progressive_audio_proxies_upstream(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50191)
    t = await create_test_track(client, "ThirdSC2", user["id"])
    tid = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == tid)
        .values(
            access_mode="third_party_stream",
            source_platform="soundcloud",
            sc_url="https://soundcloud.com/a/b",
            file_key=None,
            hls_manifest_key=None,
        )
    )
    await db_session.commit()

    async def fake_resolve(
        _tr: object,
        _sess: object,
        *,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        return "https://media.sndcdn.com/x.mp3", "progressive"

    stub = Response(
        content=b"\xff\xfb\x92",
        media_type="audio/mpeg",
    )

    with (
        patch(
            "app.api.v1.tracks.playback._resolve_third_party_stream",
            new=fake_resolve,
        ),
        patch(
            "app.api.v1.tracks.playback._http_proxy_range_get",
            new_callable=AsyncMock,
            return_value=stub,
        ),
    ):
        r = await client.get(f"/api/v1/tracks/{tid}/audio")
    assert r.status_code == 200
    assert r.content == b"\xff\xfb\x92"


async def test_soundcloud_hls_stream_and_audio_redirect(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50192)
    t = await create_test_track(client, "ThirdSCHls", user["id"])
    tid = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == tid)
        .values(
            access_mode="third_party_stream",
            source_platform="soundcloud",
            sc_url="https://soundcloud.com/x/z",
            file_key=None,
            hls_manifest_key=None,
        )
    )
    await db_session.commit()

    hls = "https://cf-hls-media.sndcdn.com/hls/123/playlist.m3u8"

    async def fake_resolve(
        _tr: object,
        _sess: object,
        *,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        return hls, "hls"

    with patch(
        "app.api.v1.tracks.playback._resolve_third_party_stream",
        new=fake_resolve,
    ):
        r = await client.get(f"/api/v1/tracks/{tid}/stream")
        r2 = await client.get(f"/api/v1/tracks/{tid}/audio")
    assert r.status_code == 200
    body = r.json()
    assert body["stream_type"] == "hls"
    assert body["url"] == hls
    assert r2.status_code == 302
    assert r2.headers["location"] == hls


async def test_recovery_handles_soundcloud_502_as_recoverable() -> None:
    from app.api.v1.tracks.playback import (
        _resolve_third_party_stream_with_recovery,
    )

    original = SimpleNamespace(
        id=100,
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/original",
    )
    replacement = SimpleNamespace(
        id=101,
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/replacement",
    )

    async def fake_resolve(
        track: object,
        _session: object,
        *,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        if track is original:
            raise HTTPException(status_code=502, detail="upstream failed")
        return "https://media.sndcdn.com/repl.mp3", "progressive"

    fallback_mock = AsyncMock(return_value=replacement)
    with (
        patch(
            "app.api.v1.tracks.playback._resolve_third_party_stream",
            new=fake_resolve,
        ),
        patch(
            "app.services.track_fallback_service.TrackFallbackService."
            "find_and_apply_fallback",
            new=fallback_mock,
        ),
        patch(
            "app.services.track_fallback_service.TrackFallbackService."
            "try_refresh_sc_url",
            new=AsyncMock(return_value=False),
        ),
    ):
        eff_track, stream_url, protocol = (
            await _resolve_third_party_stream_with_recovery(
                original,
                session=object(),  # type: ignore[arg-type]
                use_cache=True,
            )
        )

    assert eff_track is replacement
    assert stream_url == "https://media.sndcdn.com/repl.mp3"
    assert protocol == "progressive"
    fallback_mock.assert_awaited_once_with(original)
