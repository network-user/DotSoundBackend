from __future__ import annotations

from unittest import mock

import pytest

pytestmark = pytest.mark.anyio


def test_get_outbound_proxy_static_round_robin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import outbound_proxy as op

    class _Cfg:
        outbound_static_proxy_urls_list = [
            "http://127.0.0.1:1",
            "http://127.0.0.1:2",
        ]

    monkeypatch.setattr("app.services.outbound_proxy._static_rr", 0)
    monkeypatch.setattr("app.config.settings", _Cfg())

    assert op.get_outbound_proxy("soundcloud") == "http://127.0.0.1:1"
    assert op.get_outbound_proxy("soundcloud") == "http://127.0.0.1:2"
    assert op.get_outbound_proxy("bandcamp") == "http://127.0.0.1:1"


def test_get_outbound_proxy_tor_when_static_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import outbound_proxy as op

    class _Cfg:
        outbound_static_proxy_urls_list: list[str] = []

    monkeypatch.setattr("app.config.settings", _Cfg())

    fake_pool = mock.MagicMock()
    fake_pool.get_proxy.return_value = "socks5://127.0.0.1:9050"
    monkeypatch.setattr(
        "app.services.tor_pool.get_tor_pool",
        lambda: fake_pool,
    )
    assert op.get_outbound_proxy("soundcloud") == ("socks5://127.0.0.1:9050")
    fake_pool.get_proxy.assert_called_once_with("soundcloud")


def test_get_outbound_proxy_none_without_tor_or_static(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import outbound_proxy as op

    class _Cfg:
        outbound_static_proxy_urls_list: list[str] = []

    monkeypatch.setattr("app.config.settings", _Cfg())
    monkeypatch.setattr(
        "app.services.tor_pool.get_tor_pool",
        lambda: None,
    )
    assert op.get_outbound_proxy() is None


def test_outbound_proxy_configured_static(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import outbound_proxy as op

    class _Cfg:
        outbound_static_proxy_urls_list = ["http://127.0.0.1:1"]

    monkeypatch.setattr("app.config.settings", _Cfg())

    assert op.outbound_proxy_configured() is True


def test_report_outbound_proxy_result_forwards_to_tor_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import outbound_proxy as op

    fake_pool = mock.MagicMock()
    monkeypatch.setattr(
        "app.services.tor_pool.get_tor_pool",
        lambda: fake_pool,
    )

    op.report_outbound_proxy_result("socks5://127.0.0.1:9050", ok=False)

    fake_pool.report_proxy_result.assert_called_once_with(
        "socks5://127.0.0.1:9050",
        ok=False,
    )
