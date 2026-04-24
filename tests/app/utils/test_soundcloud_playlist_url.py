from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.soundcloud_playlist_url import (
    is_public_soundcloud_playlist_url,
    resolve_public_soundcloud_playlist_url,
)

pytestmark = pytest.mark.anyio


def test_is_public_accepts_www_and_m() -> None:
    assert is_public_soundcloud_playlist_url(
        "https://soundcloud.com/u/sets/mix"
    )
    assert is_public_soundcloud_playlist_url(
        "https://www.soundcloud.com/u/sets/mix"
    )
    assert is_public_soundcloud_playlist_url(
        "https://m.soundcloud.com/u/sets/mix"
    )
    assert not is_public_soundcloud_playlist_url(
        "https://on.soundcloud.com/abc123"
    )
    assert not is_public_soundcloud_playlist_url(
        "https://soundcloud.com/artist/track"
    )


async def test_resolve_returns_canonical_without_http() -> None:
    u = "https://soundcloud.com/aa/sets/bb"
    out = await resolve_public_soundcloud_playlist_url(
        u,
    )
    assert out == u


async def test_resolve_on_short_link_follows() -> None:
    final = (
        "https://soundcloud.com/artist-name/sets/playlist-slug-123"
    )
    client_cm = MagicMock()
    client_inst = MagicMock()
    client_inst.get = AsyncMock(
        return_value=MagicMock(url=final)
    )
    client_cm.__aenter__ = AsyncMock(
        return_value=client_inst
    )
    client_cm.__aexit__ = AsyncMock(
        return_value=None
    )
    with patch(
        "app.utils.soundcloud_playlist_url.httpx.AsyncClient",
        return_value=client_cm,
    ):
        out = await resolve_public_soundcloud_playlist_url(
            "https://on.soundcloud.com/YclRagcKkRtFsdf",
        )
    assert out == final
    client_inst.get.assert_awaited()


async def test_resolve_fast_rejects_main_domain_track_path() -> None:
    with patch(
        "app.utils.soundcloud_playlist_url.httpx.AsyncClient"
    ) as m:
        with pytest.raises(ValueError, match="on.soundcloud.com"):
            await resolve_public_soundcloud_playlist_url(
                "https://soundcloud.com/artist/track",
            )
    m.assert_not_called()
