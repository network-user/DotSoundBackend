from typing import Any


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

    Delegates to the internal provider adapter, wired in a follow-up
    change. Tests monkey-patch this function.
    """
    raise NotImplementedError(
        "scan_playlist_url is not yet wired to the internal provider "
        "adapter"
    )
