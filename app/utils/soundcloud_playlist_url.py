"""Validation and normalization for public SoundCloud playlist import URLs."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import httpx

# Public playlist share path: /{user}/sets/{slug}
# Includes mobile host m.soundcloud.com (resolves to same resource as www).
_SC_PLAYLIST_RE = re.compile(
    r"^https?://(?:(?:www|m)\.)?soundcloud\.com/[^/?#]+/sets/[^/?#]+",
    re.IGNORECASE,
)

# Only these (or subdomains) may be expanded via HTTP; blocks api. and open proxies.
_SC_ALLOWED_RESOLVE_HOSTS = frozenset(
    {
        "on.soundcloud.com",
        "m.soundcloud.com",
        "soundcloud.com",
        "www.soundcloud.com",
    }
)


def is_public_soundcloud_playlist_url(url: str) -> bool:
    u = (url or "").strip()
    if not u:
        return False
    return bool(_SC_PLAYLIST_RE.match(u))


def _canonical_sc_playlist_url(url: str) -> str:
    """
    Path-only playlist URL: drop utm/tracking query and #fragment,
    force https, collapse www. and m. to soundcloud.com.
    (SoundCloud resolve API and imports misbehave with share query strings.)
    """
    p = urlparse((url or "").strip())
    netloc = (p.netloc or "").lower()
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[-1]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc == "m.soundcloud.com":
        netloc = "soundcloud.com"
    scheme = p.scheme.lower() if p.scheme else "https"
    if scheme in ("http", "https"):
        scheme = "https"
    p2 = p._replace(
        scheme=scheme,
        netloc=netloc,
        query="",
        fragment="",
    )
    return urlunparse(p2)


def _netloc_host(netloc: str) -> str:
    h = (netloc or "").lower().split("@")[-1]
    if ":" in h:
        h = h.rsplit(":", 1)[0]
    return h


def _is_soundcloud_resolvable_host(host: str) -> bool:
    h = (host or "").lower()
    if h in ("api.soundcloud.com",):
        return False
    if h in _SC_ALLOWED_RESOLVE_HOSTS:
        return True
    if h.endswith(".soundcloud.com") and not h.startswith("api."):
        return True
    return False


async def _follow_to_final_url(url: str) -> str:
    """GET with redirects; return final URL (fragment stripped)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20.0,
        headers=headers,
    ) as client:
        r = await client.get(url)
    r.raise_for_status()
    return _canonical_sc_playlist_url(str(r.url))


async def resolve_public_soundcloud_playlist_url(
    url: str,
) -> str:
    """
    Return a canonical https://soundcloud.com/.../sets/... URL.

    - Full ``.../sets/...`` links are returned canonical
      (https, no ``?ref=`` / UTM / ``#``, ``m.`` → ``soundcloud.com``).
    - ``on.soundcloud.com/...`` and other resolvable SC hosts are followed until
      a .../sets/... page is reached (or validation fails).
    """
    u = (url or "").strip()
    if not u:
        msg = "URL is required"
        raise ValueError(msg)
    c0 = _canonical_sc_playlist_url(u)
    if is_public_soundcloud_playlist_url(c0):
        return c0
    try:
        parsed = urlparse(u)
    except ValueError as exc:
        msg = "Invalid URL"
        raise ValueError(msg) from exc
    if parsed.scheme not in ("http", "https"):
        msg = "URL must use http or https"
        raise ValueError(msg)
    host = _netloc_host(parsed.netloc)
    if host in (
        "soundcloud.com",
        "www.soundcloud.com",
    ) and "/sets/" not in (parsed.path or ""):
        msg = (
            "URL must be a public soundcloud.com playlist link "
            "(.../sets/...), or use an on.soundcloud.com share link."
        )
        raise ValueError(msg)
    if not _is_soundcloud_resolvable_host(host):
        msg = (
            "URL must be a soundcloud.com playlist link, "
            "or a share link such as on.soundcloud.com/…"
        )
        raise ValueError(msg)
    try:
        final = await _follow_to_final_url(u)
    except httpx.HTTPError as exc:
        msg = "Could not open this SoundCloud link. Check that it is valid and public."
        raise ValueError(msg) from exc
    cfinal = _canonical_sc_playlist_url(final)
    if not is_public_soundcloud_playlist_url(cfinal):
        msg = (
            "This link does not resolve to a public playlist "
            "(URL must contain /sets/ on soundcloud.com)."
        )
        raise ValueError(msg)
    return cfinal
