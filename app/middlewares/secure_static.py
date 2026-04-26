"""Middleware that gates access to admin-only static assets.

Any request targeting ``/mini_app/assets/secure/*`` must carry a
valid signed token (``?t=...``) bound to the requesting admin.
Anything else receives a 404, so non-admins cannot tell whether
the file exists.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.admin_manifest_service import (
    verify_bundle_token,
)


class SecureStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if "/mini_app/assets/secure/" not in path:
            return await call_next(request)

        token = request.query_params.get("t", "")
        user_id_raw = request.query_params.get("u", "")
        try:
            user_id = int(user_id_raw or 0)
        except ValueError:
            user_id = 0

        if not token or user_id <= 0:
            return Response(status_code=404)
        if not verify_bundle_token(token, user_id):
            return Response(status_code=404)
        return await call_next(request)
