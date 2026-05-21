from collections.abc import AsyncIterator
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
    db_session: AsyncSession,
) -> None:
    """A freshly uploaded UGC track now has a provisional ``file_key``
    pointing at the raw S3 object so it can be played before the
    transcode finishes; the 422 branch only fires when something has
    actually wiped the key (corrupt row, admin-side cleanup).
    """
    user = await create_test_user(client, 50001)
    track = await create_test_track(client, "StreamMe", user["id"])
    track_id = track["id"]
    await db_session.execute(
        update(Track).where(Track.id == track_id).values(file_key=None)
    )
    await db_session.commit()

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

    video_meta = SimpleNamespace(
        content_length=len(video_bytes),
        content_range=None,
        content_type="video/mp4",
        etag="vid123",
        last_modified=None,
        accept_ranges="bytes",
    )

    async def _video_body() -> AsyncIterator[bytes]:
        yield video_bytes

    with patch(
        "app.core.s3.open_object_range",
        new_callable=AsyncMock,
        return_value=(video_meta, _video_body()),
    ) as mock_range:
        r = await client.get(f"/api/v1/tracks/{t['id']}/video")
    assert r.status_code == 200
    mock_range.assert_awaited_once_with("videos/px1.mp4", None)
    assert r.content == video_bytes
    assert r.headers["content-type"] == "video/mp4"
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["etag"] == '"vid123"'


async def test_video_proxy_supports_range_requests(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50022)
    t = await create_test_track(client, "VidRange", user["id"])
    await db_session.execute(
        update(Track)
        .where(Track.id == t["id"])
        .values(video_key="video-blobs/aa/range.mp4")
    )
    await db_session.commit()

    video_chunk = b"ftyp"
    video_meta = SimpleNamespace(
        content_length=len(video_chunk),
        content_range="bytes 0-3/104",
        content_type="video/mp4",
        etag=None,
        last_modified=None,
        accept_ranges="bytes",
    )

    async def _video_body() -> AsyncIterator[bytes]:
        yield video_chunk

    with patch(
        "app.core.s3.open_object_range",
        new_callable=AsyncMock,
        return_value=(video_meta, _video_body()),
    ) as mock_range:
        r = await client.get(
            f"/api/v1/tracks/{t['id']}/video",
            headers={"Range": "bytes=0-3"},
        )

    assert r.status_code == 206
    mock_range.assert_awaited_once_with(
        "video-blobs/aa/range.mp4",
        "bytes=0-3",
    )
    assert r.content == video_chunk
    assert r.headers["content-range"] == "bytes 0-3/104"
    assert r.headers["content-length"] == str(len(video_chunk))
    assert (
        r.headers["cache-control"]
        == "public, max-age=31536000, immutable"
    )


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
    db_session: AsyncSession,
) -> None:
    """422 only when ``file_key`` is genuinely missing; uploads now
    write the provisional raw key so the player never sees this case
    while the transcode is still pending.
    """
    user = await create_test_user(client, 50018)
    t = await create_test_track(client, "NoAudio", user["id"])
    await db_session.execute(
        update(Track).where(Track.id == t["id"]).values(file_key=None)
    )
    await db_session.commit()

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
    meta = SimpleNamespace(
        content_length=len(mp3),
        content_range=None,
        content_type="audio/mpeg",
        etag="abc123",
        last_modified=None,
        accept_ranges="bytes",
    )

    async def _body() -> AsyncIterator[bytes]:
        yield mp3

    with patch(
        "app.core.s3.open_object_range",
        new_callable=AsyncMock,
        return_value=(meta, _body()),
    ):
        r = await client.get(
            f"/api/v1/tracks/{track_id}/audio" f"?force_progressive=true"
        )
    assert r.status_code == 200
    assert r.content == mp3
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.headers["etag"] == '"abc123"'
    assert r.headers["accept-ranges"] == "bytes"
    assert "cache-control" in r.headers


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


async def test_http_proxy_range_get_uses_streaming_egress_pool() -> None:
    from app.api.v1.tracks import playback as mod
    from app.config import settings as _settings
    from app.services.streaming_egress_pool import (
        get_streaming_egress_pool,
    )

    class _UpstreamResponse:
        status_code = 200
        headers = {
            "content-type": "audio/mpeg",
            "content-length": "3",
        }

        async def aiter_bytes(self, _size: int) -> AsyncIterator[bytes]:
            yield b"abc"

        async def aclose(self) -> None:
            return None

    fake_client = SimpleNamespace(
        build_request=lambda *args, **kwargs: object(),
        send=AsyncMock(return_value=_UpstreamResponse()),
        aclose=AsyncMock(),
    )
    pool = get_streaming_egress_pool()
    pool.reset_for_tests()
    proxy_url = "http://10.0.0.1:8080"
    original = _settings.streaming_proxy_out_urls
    _settings.streaming_proxy_out_urls = proxy_url
    try:
        with patch(
            "app.api.v1.tracks.playback.httpx.AsyncClient",
            return_value=fake_client,
        ) as client_cls:
            response = await mod._http_proxy_range_get(
                SimpleNamespace(headers={}),  # type: ignore[arg-type]
                "https://media.sndcdn.com/x.mp3",
                detail_fail="fail",
                detail_error="error",
                proxy_service="soundcloud",
                sticky_key="track:99",
            )
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

        assert body == b"abc"
        assert client_cls.call_args.kwargs["proxy"] == proxy_url
        assert "content-length" not in response.headers
    finally:
        _settings.streaming_proxy_out_urls = original
        pool.reset_for_tests()


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


async def test_soundcloud_resolver_prefers_progressive_stream(
    db_session: AsyncSession,
) -> None:
    from app.api.v1.tracks import playback as mod

    with patch(
        "app.services.soundcloud_service.SoundCloudService.get_stream_info",
        new=AsyncMock(
            return_value=(
                "https://media.sndcdn.com/x.mp3",
                "progressive",
            ),
        ),
    ) as get_stream_info:
        result = await mod._resolve_third_party_stream(
            SimpleNamespace(
                source_platform="soundcloud",
                sc_url="https://soundcloud.com/x/z",
            ),
            db_session,
        )

    assert result == ("https://media.sndcdn.com/x.mp3", "progressive")
    assert get_stream_info.await_args.kwargs["prefer_hls"] is False


async def test_soundcloud_stream_failure_returns_diagnostics(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50193)
    t = await create_test_track(client, "ThirdSCFail", user["id"])
    tid = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == tid)
        .values(
            access_mode="third_party_stream",
            catalog_type="external_reference",
            source_platform="soundcloud",
            sc_url="https://soundcloud.com/x/fail",
            file_key=None,
            hls_manifest_key=None,
        )
    )
    await db_session.commit()

    detail = {
        "code": "soundcloud_stream_unavailable",
        "message": "SoundCloud stream unavailable",
        "reason": "provider_manifest_not_found_for_all_formats",
        "stage": "transcoding_manifest",
        "upstream_status": 404,
        "attempted_protocols": ["progressive", "hls"],
        "retryable": True,
    }

    with patch(
        "app.api.v1.tracks.playback."
        "_resolve_third_party_stream_with_recovery",
        new=AsyncMock(
            side_effect=HTTPException(status_code=502, detail=detail),
        ),
    ):
        r = await client.get(f"/api/v1/tracks/{tid}/stream")

    assert r.status_code == 502
    body = r.json()
    assert body["detail"]["code"] == "soundcloud_stream_unavailable"
    assert body["detail"]["reason"] == (
        "provider_manifest_not_found_for_all_formats"
    )
    assert body["detail"]["track_id"] == tid
    assert body["detail"]["source_platform"] == "soundcloud"
    assert body["detail"]["access_mode"] == "third_party_stream"
    assert body["detail"]["catalog_type"] == "external_reference"
    assert body["detail"]["attempted_protocols"] == ["progressive", "hls"]


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


async def test_sc_502_manifest_all_404_triggers_url_refresh() -> None:
    from app.api.v1.tracks.playback import (
        _resolve_third_party_stream_with_recovery,
    )

    track = SimpleNamespace(
        id=200,
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/a/original",
    )
    call_log: list[str] = []

    async def fake_resolve(
        track: object,
        _session: object,
        *,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        call_log.append("resolve")
        if len(call_log) == 1:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "soundcloud_stream_unavailable",
                    "reason": ("provider_manifest_not_found_for_all_formats"),
                },
            )
        return "https://media.sndcdn.com/refreshed.mp3", "hls"

    refresh_mock = AsyncMock(return_value=True)
    fallback_mock = AsyncMock(return_value=None)
    with (
        patch(
            "app.api.v1.tracks.playback._resolve_third_party_stream",
            new=fake_resolve,
        ),
        patch(
            "app.services.track_fallback_service.TrackFallbackService."
            "try_refresh_sc_url",
            new=refresh_mock,
        ),
        patch(
            "app.services.track_fallback_service.TrackFallbackService."
            "find_and_apply_fallback",
            new=fallback_mock,
        ),
    ):
        eff_track, stream_url, protocol = (
            await _resolve_third_party_stream_with_recovery(
                track,
                session=object(),  # type: ignore[arg-type]
                use_cache=True,
            )
        )

    assert eff_track is track
    assert stream_url == "https://media.sndcdn.com/refreshed.mp3"
    assert protocol == "hls"
    refresh_mock.assert_awaited_once_with(track)
    fallback_mock.assert_not_awaited()


async def test_stream_returns_hls_url_for_internal_hls_track(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50231)
    t = await create_test_track(client, "InternalHls", user["id"])
    track_id = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(
            hls_manifest_key=f"hls-blobs/aa/sha/{track_id}/master.m3u8",
            audio_cache_status="pending",
        )
    )
    await db_session.commit()

    r = await client.get(f"/api/v1/tracks/{track_id}/stream")
    assert r.status_code == 200
    body = r.json()
    assert body["stream_type"] == "hls"
    assert body["url"] == f"/api/v1/tracks/{track_id}/hls/master.m3u8"
    assert body["track_id"] == track_id


async def test_audio_hls_redirect_includes_link_preload_header(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 50232)
    t = await create_test_track(client, "HlsLinkPreload", user["id"])
    track_id = t["id"]
    await db_session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(
            hls_manifest_key=f"hls/{track_id}/master.m3u8",
            file_key=f"anon/playback-link-{track_id}.mp3",
        )
    )
    await db_session.commit()

    r = await client.get(
        f"/api/v1/tracks/{track_id}/audio",
        follow_redirects=False,
    )
    assert r.status_code == 302
    expected_url = f"/api/v1/tracks/{track_id}/hls/master.m3u8"
    assert r.headers["location"].endswith(expected_url)
    link = r.headers.get("link", "")
    assert expected_url in link
    assert "rel=preload" in link
    assert "as=fetch" in link
