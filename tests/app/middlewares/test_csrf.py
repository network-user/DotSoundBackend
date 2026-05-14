"""Smoke tests for the CSRF double-submit middleware.

We avoid issuing a real session token here — the middleware runs
before the auth dependency, so we can tell CSRF apart from auth by
the status code:

- ``403 {"detail": "CSRF token missing or invalid"}`` means the
  middleware itself rejected the request.
- ``401`` means CSRF let the request through and the auth layer
  rejected it afterwards (which is the outcome we expect for every
  bypass path under test).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


_MUTATING_PATH = "/api/v1/onboarding/replay"


async def test_safe_method_skips_csrf(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200


async def test_post_without_session_cookie_is_not_blocked_by_csrf(
    client: AsyncClient,
) -> None:
    res = await client.post(_MUTATING_PATH)
    assert res.status_code == 401
    body = res.json()
    assert "CSRF" not in (body.get("detail") or "")


async def test_post_with_session_cookie_and_no_csrf_token_is_blocked(
    client: AsyncClient,
) -> None:
    res = await client.post(
        _MUTATING_PATH,
        cookies={"ds_access": "dummy-cookie-value"},
    )
    assert res.status_code == 403
    assert "CSRF" in (res.json().get("detail") or "")


async def test_post_with_matching_csrf_pair_is_not_blocked(
    client: AsyncClient,
) -> None:
    res = await client.post(
        _MUTATING_PATH,
        cookies={
            "ds_access": "dummy-cookie-value",
            "ds_csrf": "csrf-token-value",
        },
        headers={"X-CSRF-Token": "csrf-token-value"},
    )
    assert res.status_code == 401


async def test_bearer_auth_bypasses_csrf_even_with_session_cookie(
    client: AsyncClient,
) -> None:
    res = await client.post(
        _MUTATING_PATH,
        cookies={"ds_access": "dummy-cookie-value"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert res.status_code == 401
    assert "CSRF" not in (res.json().get("detail") or "")


async def test_exempt_prefix_skips_csrf(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/telegram",
        cookies={"ds_access": "dummy-cookie-value"},
        json={"init_data": ""},
    )
    assert res.status_code != 403 or "CSRF" not in (
        res.json().get("detail") or ""
    )
