"""Helpers for moving the access-token from response body to httpOnly cookie.

This is the server-side half of the F1 hardening: once the frontend
switches to ``credentials: 'include'`` and stops reading the token
from JSON, removing it from the response body will close the
XSS-via-localStorage attack surface. Until then, both transports
coexist so deployments can roll forward independently.
"""

from __future__ import annotations

from fastapi import Response

from app.config import settings

ACCESS_COOKIE_NAME = "ds_access"


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expire_days * 24 * 3600,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        path="/",
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
    )
