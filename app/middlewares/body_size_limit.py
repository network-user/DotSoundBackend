"""Body-size cap.

Rejects requests whose Content-Length exceeds the configured limit
before they reach the handler. Routes that legitimately need larger
bodies (audio/avatar upload) can opt out by prefix.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 2 MiB default — covers JSON API and most signed requests with margin.
_DEFAULT_LIMIT_BYTES = 2 * 1024 * 1024

# Upload routes that legitimately need a larger body.
_UPLOAD_PREFIXES = (
    "/api/v1/users/me/avatar",
    "/api/v1/tracks/upload",
    "/api/v1/admin/upload",
    "/api/v1/internal/audio-compute/audio",
)
_UPLOAD_LIMIT_BYTES = 100 * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        default_bytes: int = _DEFAULT_LIMIT_BYTES,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._default = default_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        limit = self._limit_for(request.url.path)
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                size = int(cl)
            except ValueError:
                return JSONResponse(
                    {"detail": "invalid content-length"},
                    status_code=400,
                )
            if size > limit:
                return JSONResponse(
                    {"detail": "request body too large"},
                    status_code=413,
                )
        return await call_next(request)

    def _limit_for(self, path: str) -> int:
        for prefix in _UPLOAD_PREFIXES:
            if path.startswith(prefix):
                return _UPLOAD_LIMIT_BYTES
        return self._default
