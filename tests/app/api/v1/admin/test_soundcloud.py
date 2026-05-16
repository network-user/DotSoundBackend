from app.api.v1.admin.soundcloud import (
    _playlist_summary,
    _redact_manifest_line,
)


def test_playlist_summary_detects_encrypted_hls() -> None:
    summary = _playlist_summary(
        "\n".join(
            [
                "#EXTM3U",
                "#EXT-X-VERSION:7",
                (
                    "#EXT-X-KEY:METHOD=SAMPLE-AES,"
                    'URI="https://keys.example/key?k=secret",'
                    'KEYFORMAT="com.apple.streamingkeydelivery"'
                ),
                "#EXTINF:6.0,",
                "https://cdn.example/seg.m4s?token=secret",
            ]
        )
    )

    assert summary["is_hls"] is True
    assert summary["has_ext_x_key"] is True
    assert summary["key_methods"] == ["SAMPLE-AES"]
    assert summary["keyformats"] == ["com.apple.streamingkeydelivery"]
    assert any(
        'URI="https://keys.example/key?..."' in line
        for line in summary["preview_lines"]
    )
    assert "https://cdn.example/seg.m4s?..." in summary["preview_lines"]


def test_redact_manifest_line_keeps_non_url_lines() -> None:
    assert _redact_manifest_line("#EXT-X-VERSION:7") == "#EXT-X-VERSION:7"
