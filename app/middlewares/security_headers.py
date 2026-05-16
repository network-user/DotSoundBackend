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
        elif ct.startswith("text/html"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' "
                "https://telegram.org; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' data:; "
                "media-src 'self' blob: https:; "
                "connect-src 'self' ws: wss: https:; "
                "worker-src 'self' blob:; "
                "frame-src 'self' https://telegram.org "
                "https://w.soundcloud.com; "
                "frame-ancestors 'self' https://web.telegram.org; "
                "base-uri 'self'; "
                "form-action 'self'",
            )
        return response
