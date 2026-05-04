import asyncio
import concurrent.futures
from typing import Any

import structlog
from dotsound_private_core.services import (
    PlaylistScanResult,
    fetch_external_playlist,
)

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_scan_executor: concurrent.futures.ThreadPoolExecutor | None = None


def _get_scan_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Return the module-level bounded scan executor, creating it once.

    A dedicated pool with a capped worker count prevents the default
    ThreadPoolExecutor from spawning unbounded threads when many users
    trigger simultaneous yt-dlp playlist scans.
    """
    global _scan_executor
    if _scan_executor is None:
        max_workers = max(1, settings.scan_executor_max_workers)
        _scan_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="scan_worker",
        )
        logger.info(
            "scan_executor_created",
            max_workers=max_workers,
        )
    return _scan_executor


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
    Runs ``fetch_external_playlist`` in a bounded thread pool to cap
    concurrent yt-dlp threads under high load.
    """
    loop = asyncio.get_event_loop()
    result: PlaylistScanResult = await loop.run_in_executor(
        _get_scan_executor(),
        fetch_external_playlist,
        source,
        url,
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
