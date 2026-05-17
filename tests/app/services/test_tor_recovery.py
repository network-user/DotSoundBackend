"""Unit tests for the Tor circuit auto-recovery loop."""

from __future__ import annotations

from unittest import mock

import pytest

from app.services import tor_recovery

pytestmark = pytest.mark.anyio


async def _stub_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    pool_enabled: bool = True,
    threshold: int = 3,
    interval: float = 60.0,
) -> None:
    fake = mock.MagicMock()
    fake.tor_recovery_enabled = enabled
    fake.tor_pool_enabled = pool_enabled
    fake.tor_recovery_failure_threshold = threshold
    fake.tor_recovery_min_interval_s = interval
    monkeypatch.setattr(tor_recovery, "settings", fake)


async def _stub_pool(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pool: object | None,
) -> None:
    monkeypatch.setattr(
        "app.services.tor_pool.get_tor_pool",
        lambda: pool,
    )


async def test_recovery_disabled_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await tor_recovery.reset_state_for_tests()
    await _stub_settings(monkeypatch, enabled=False)
    triggered = await tor_recovery.note_outbound_exhaustion("soundcloud")
    assert triggered is False


async def test_recovery_skipped_when_pool_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await tor_recovery.reset_state_for_tests()
    await _stub_settings(monkeypatch, pool_enabled=False)
    triggered = await tor_recovery.note_outbound_exhaustion("soundcloud")
    assert triggered is False


async def test_threshold_must_be_reached_to_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await tor_recovery.reset_state_for_tests()
    await _stub_settings(monkeypatch, threshold=3, interval=0.0)
    pool = mock.MagicMock()
    pool.force_newnym = mock.AsyncMock(return_value=True)
    await _stub_pool(monkeypatch, pool=pool)

    assert await tor_recovery.note_outbound_exhaustion("soundcloud") is False
    assert await tor_recovery.note_outbound_exhaustion("soundcloud") is False
    assert await tor_recovery.note_outbound_exhaustion("soundcloud") is True

    pool.force_newnym.assert_called_once()


async def test_success_resets_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await tor_recovery.reset_state_for_tests()
    await _stub_settings(monkeypatch, threshold=2, interval=0.0)
    pool = mock.MagicMock()
    pool.force_newnym = mock.AsyncMock(return_value=True)
    await _stub_pool(monkeypatch, pool=pool)

    assert await tor_recovery.note_outbound_exhaustion("soundcloud") is False
    await tor_recovery.note_outbound_success("soundcloud")
    assert await tor_recovery.note_outbound_exhaustion("soundcloud") is False
    pool.force_newnym.assert_not_called()


async def test_recovery_throttled_after_recent_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await tor_recovery.reset_state_for_tests()
    await _stub_settings(monkeypatch, threshold=1, interval=300.0)
    pool = mock.MagicMock()
    pool.force_newnym = mock.AsyncMock(return_value=True)
    await _stub_pool(monkeypatch, pool=pool)

    first = await tor_recovery.note_outbound_exhaustion("soundcloud")
    second = await tor_recovery.note_outbound_exhaustion("soundcloud")

    assert first is True
    assert second is False
    pool.force_newnym.assert_called_once()


async def test_recovery_skipped_when_pool_not_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await tor_recovery.reset_state_for_tests()
    await _stub_settings(monkeypatch, threshold=1, interval=0.0)
    await _stub_pool(monkeypatch, pool=None)

    triggered = await tor_recovery.note_outbound_exhaustion("soundcloud")
    assert triggered is False
