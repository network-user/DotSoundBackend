from collections.abc import Awaitable, Callable

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request], Awaitable[Response]
        ],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = (
            "nosniff"
        )
        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )
        response.headers.setdefault(
            "X-Frame-Options", "DENY"
        )
        response.headers.setdefault(
            "X-Permitted-Cross-Domain-Policies", "none"
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), "
            "interest-cohort=()",
        )
        if not settings.debug:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        ct = response.headers.get("content-type", "")
        if ct.startswith(
            ("audio/", "video/", "image/")
        ):
            response.headers[
                "Content-Security-Policy"
            ] = "default-src 'none'"
        return response
