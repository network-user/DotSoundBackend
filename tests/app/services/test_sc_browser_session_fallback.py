"""Catalog/API direct-fallback tests for ``sc_get_with_anti_block``.

When the OutboundClient pool reports every Tor / static identity as
quarantined (``OutboundExhaustedError``), the helper retries once
from the server's native IP — provided the operator has opted in
via ``SC_CATALOG_DIRECT_FALLBACK_ON_EXHAUSTION`` (default on). This
test exercises both the success and the failure of that fallback,
plus the opt-out path.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from dotsound_private_core.services.outbound.errors import (
    OutboundExhaustedError,
)
from dotsound_private_core.services.sc_anti_block_policy import ScErrorKind

from app.services import sc_browser_session
from app.services.sc_browser_session import (
    ScBrowserResponse,
    sc_get_with_anti_block,
)


class _ExhaustedClientCM:
    """Async context manager whose ``get`` always raises exhausted."""

    async def __aenter__(self) -> _ExhaustedClientCM:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, *_: object, **__: object) -> object:
        raise OutboundExhaustedError("all identities quarantined")


@pytest.fixture(autouse=True)
def _patch_outbound_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sc_browser_session.OutboundClient,
        "for_service",
        classmethod(lambda cls, *a, **kw: _ExhaustedClientCM()),
    )


@pytest.fixture(autouse=True)
def _no_dead_track_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _is_dead(_: object) -> bool:
        return False

    monkeypatch.setattr(
        sc_browser_session.sc_dead_track_cache, "is_dead", _is_dead
    )


@pytest.mark.anyio
async def test_direct_fallback_success_when_pool_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings as app_settings

    monkeypatch.setattr(
        app_settings,
        "sc_catalog_direct_fallback_on_exhaustion",
        True,
        raising=False,
    )

    direct_response = ScBrowserResponse(
        status_code=200,
        text='{"id": 6705}',
        content=b'{"id": 6705}',
        headers={},
        url="https://api-v2.soundcloud.com/tracks/6705",
        identity="direct_fallback",
    )

    async def _fake_direct(
        url: str, *, params: object, headers: object, timeout_s: float
    ) -> ScBrowserResponse:
        return direct_response

    monkeypatch.setattr(
        sc_browser_session, "_direct_get_fallback", _fake_direct
    )

    with patch(
        "app.core.observability.sc_direct_fallback_observed"
    ) as mock_metric:
        outcome = await sc_get_with_anti_block(
            "https://api-v2.soundcloud.com/tracks/6705",
            sticky_key="sc:track:6705",
        )

    assert outcome.error_kind is ScErrorKind.OK
    assert outcome.response is direct_response
    mock_metric.assert_called_once_with(ok=True)


@pytest.mark.anyio
async def test_direct_fallback_returns_burned_when_direct_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings as app_settings

    monkeypatch.setattr(
        app_settings,
        "sc_catalog_direct_fallback_on_exhaustion",
        True,
        raising=False,
    )

    async def _fake_direct(
        url: str, *, params: object, headers: object, timeout_s: float
    ) -> None:
        return None

    monkeypatch.setattr(
        sc_browser_session, "_direct_get_fallback", _fake_direct
    )

    with patch(
        "app.core.observability.sc_direct_fallback_observed"
    ) as mock_metric:
        outcome = await sc_get_with_anti_block(
            "https://api-v2.soundcloud.com/tracks/6705",
            sticky_key="sc:track:6705",
        )

    assert outcome.error_kind is ScErrorKind.CIRCUIT_BURNED
    assert outcome.response is None
    mock_metric.assert_called_once_with(ok=False)


@pytest.mark.anyio
async def test_direct_fallback_skipped_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings as app_settings

    monkeypatch.setattr(
        app_settings,
        "sc_catalog_direct_fallback_on_exhaustion",
        False,
        raising=False,
    )

    direct_called = {"count": 0}

    async def _fake_direct(*_: object, **__: object) -> None:
        direct_called["count"] += 1
        return None

    monkeypatch.setattr(
        sc_browser_session, "_direct_get_fallback", _fake_direct
    )

    outcome = await sc_get_with_anti_block(
        "https://api-v2.soundcloud.com/tracks/6705",
        sticky_key="sc:track:6705",
    )

    assert outcome.error_kind is ScErrorKind.CIRCUIT_BURNED
    assert direct_called["count"] == 0
