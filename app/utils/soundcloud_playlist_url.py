"""Validation for public SoundCloud playlist share URLs (import)."""

from __future__ import annotations

import re

# Public playlist share path: /{user}/sets/{slug}
_SC_PLAYLIST_RE = re.compile(
    r"^https?://(?:www\.)?soundcloud\.com/[^/?#]+/sets/[^/?#]+",
    re.IGNORECASE,
)


def is_public_soundcloud_playlist_url(url: str) -> bool:
    u = (url or "").strip()
    return bool(_SC_PLAYLIST_RE.match(u))
