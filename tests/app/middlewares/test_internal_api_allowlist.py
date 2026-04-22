"""Tests for the internal API IP allowlist middleware."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_health_endpoint_unaffected(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200


async def test_internal_path_blocked_when_no_allowlist(
    client: AsyncClient,
) -> None:
    with patch(
        "app.middlewares.internal_api_allowlist.is_ip_in_cidrs",
        return_value=False,
    ):
        r = await client.post(
            "/api/v1/internal/audio-compute/jobs/claim"
        )
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


async def test_internal_path_allowed_when_ip_matches(
    client: AsyncClient,
) -> None:
    with patch(
        "app.middlewares.internal_api_allowlist.is_ip_in_cidrs",
        return_value=True,
    ):
        r = await client.post(
            "/api/v1/internal/audio-compute/jobs/claim"
        )
    assert r.status_code != 404 or r.json().get(
        "detail"
    ) != "Not Found"


async def test_non_internal_path_unaffected_by_allowlist(
    client: AsyncClient,
) -> None:
    with patch(
        "app.middlewares.internal_api_allowlist.is_ip_in_cidrs",
        return_value=False,
    ):
        r = await client.get("/api/v1/health")
    assert r.status_code == 200
