from app.services.youtube_service import _yt_pick_stream_url


def test_yt_pick_skips_top_level_m3u8_uses_format_list() -> None:
    info: dict = {
        "id": "x",
        "url": "https://x.test/api/manifest/hls_variant/.../file/index.m3u8",
        "formats": [
            {
                "acodec": "mp4a.40.2",
                "vcodec": "none",
                "url": "https://r1---sn-xxx.googlevideo.com/videoplayback/abc.140",
                "tbr": 128,
            },
        ],
    }
    picked = _yt_pick_stream_url(info)
    assert picked is not None
    u, _meta = picked
    assert "m3u8" not in u.lower()
    assert "140" in u or "googlevideo" in u
