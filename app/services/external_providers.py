import asyncio
from typing import Any

from dotsound_private_core.services import (
    PlaylistScanResult,
    fetch_external_playlist,
)


class ProviderError(Exception):
    """Structured error raised by the external-provider adapter.

    ``code`` is one of ``not_found``, ``private``, ``invalid_url``,
    ``provider_unavailable`` and is safe to forward to the client so
    the UI can render a localized message.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


ALLOWED_ERROR_CODES: frozenset[str] = frozenset(
    {
        "not_found",
        "private",
        "invalid_url",
        "provider_unavailable",
    }
)


async def scan_playlist_url(
    source: str, url: str
) -> dict[str, Any]:
    """Return a normalized track list for an external playlist/album URL.

    Shape::

        {
            "kind": "playlist" | "album",
            "tracks": [
                {"title": str, "artist": str | None,
                 "duration_seconds": int | None},
                ...
            ],
        }

    Raises :class:`ProviderError` on non-``ok`` status. The actual
    upstream call lives in the private core; this adapter only
    normalizes shapes and maps opaque status codes to exceptions.
    """
    result: PlaylistScanResult = await asyncio.to_thread(
        fetch_external_playlist, source, url
    )

    if result.status == "ok":
        return {
            "kind": result.kind,
            "tracks": [
                {
                    "title": t.title,
                    "artist": t.artist,
                    "duration_seconds": t.duration_seconds,
                    "external_id": t.external_id,
                }
                for t in result.tracks
            ],
        }

    code = (
        result.status
        if result.status in ALLOWED_ERROR_CODES
        else "provider_unavailable"
    )
    raise ProviderError(
        code=code,
        message=result.error_message or code,
    )
