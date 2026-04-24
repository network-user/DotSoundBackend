"""Validation for public Spotify album/playlist open links (import)."""

from __future__ import annotations

import re

_SPOTIFY_PLAYLIST = re.compile(
    r"^https?://open\.spotify\.com/playlist/[A-Za-z0-9]+",
    re.IGNORECASE,
)
_SPOTIFY_ALBUM = re.compile(
    r"^https?://open\.spotify\.com/album/[A-Za-z0-9]+",
    re.IGNORECASE,
)


def is_open_spotify_playlist_or_album_url(url: str) -> bool:
    u = (url or "").strip()
    if not u:
        return False
    return bool(_SPOTIFY_PLAYLIST.match(u) or _SPOTIFY_ALBUM.match(u))
