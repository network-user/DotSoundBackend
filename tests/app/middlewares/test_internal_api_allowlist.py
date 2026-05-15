"""Tests for the internal API IP allowlist middleware."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import settings

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
        r = await client.post("/api/v1/internal/audio-compute/jobs/claim")
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


async def test_internal_path_allowed_when_ip_matches(
    client: AsyncClient,
) -> None:
    with patch(
        "app.middlewares.internal_api_allowlist.is_ip_in_cidrs",
        return_value=True,
    ):
        r = await client.post("/api/v1/internal/audio-compute/jobs/claim")
    assert r.status_code != 404 or r.json().get("detail") != "Not Found"


async def test_non_internal_path_unaffected_by_allowlist(
    client: AsyncClient,
) -> None:
    with patch(
        "app.middlewares.internal_api_allowlist.is_ip_in_cidrs",
        return_value=False,
    ):
        r = await client.get("/api/v1/health")
    assert r.status_code == 200


async def test_internal_path_uses_forwarded_ip_from_trusted_proxy(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "internal_api_allowed_cidrs",
        "203.0.113.10/32",
    )
    monkeypatch.setattr(settings, "internal_api_trusted_proxies", "")
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "127.0.0.1/32")

    r = await client.post(
        "/api/v1/internal/audio-compute/jobs/claim",
        headers={
            "X-Forwarded-For": ("198.51.100.66, 203.0.113.10"),
        },
    )

    assert r.status_code == 401


async def test_internal_path_ignores_forwarded_ip_without_trusted_proxy(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "internal_api_allowed_cidrs",
        "203.0.113.10/32",
    )
    monkeypatch.setattr(settings, "internal_api_trusted_proxies", "")
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "")

    r = await client.post(
        "/api/v1/internal/audio-compute/jobs/claim",
        headers={"X-Forwarded-For": "203.0.113.10"},
    )

    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}
