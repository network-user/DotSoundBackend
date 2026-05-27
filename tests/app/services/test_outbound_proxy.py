from __future__ import annotations

from unittest import mock

import httpx
import pytest

pytestmark = pytest.mark.anyio


def test_proxy_url_for_httpx_normalizes_socks5h() -> None:
    from app.services.outbound_proxy import proxy_url_for_httpx

    assert (
        proxy_url_for_httpx("socks5h://user:pass@proxy.example:1080")
        == "socks5://user:pass@proxy.example:1080"
    )
    assert proxy_url_for_httpx("http://127.0.0.1:8080") == (
        "http://127.0.0.1:8080"
    )
    assert proxy_url_for_httpx(None) is None


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


async def test_instrument_httpx_hooks_record_privatecore_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dotsound_private_core.services.outbound import metrics

    from app.services import outbound_proxy as op

    metrics.reset_for_tests()
    fake_pool = mock.MagicMock()
    fake_pool.describe_proxy.return_value = {
        "transport": "tor",
        "identity": "tor:c0",
        "egress_ip": "203.0.113.44",
    }
    monkeypatch.setattr(
        "app.services.tor_pool.get_tor_pool",
        lambda: fake_pool,
    )
    kwargs: dict = {}

    op.instrument_httpx_client_kwargs(
        kwargs,
        service="soundcloud",
        proxy_url="socks5://127.0.0.1:9050",
    )
    request = httpx.Request(
        "GET",
        "https://api.soundcloud.com/tracks?secret=hidden",
    )
    for hook in kwargs["event_hooks"]["request"]:
        await hook(request)
    response = httpx.Response(200, request=request)
    for hook in kwargs["event_hooks"]["response"]:
        await hook(response)

    snapshot = metrics.snapshot_metrics()
    recent = snapshot["recent_requests"][0]
    assert snapshot["requests_total"]["soundcloud"] == 1
    assert snapshot["responses_by_status"]["soundcloud"]["2xx"] == 1
    assert recent["service"] == "soundcloud"
    assert recent["transport"] == "tor"
    assert recent["identity"] == "tor:c0"
    assert recent["egress_ip"] == "203.0.113.44"
    assert recent["host"] == "api.soundcloud.com"
    assert recent["path"] == "/tracks"
    metrics.reset_for_tests()


def test_record_outbound_proxy_error_records_recent_error() -> None:
    from dotsound_private_core.services.outbound import metrics

    from app.services import outbound_proxy as op

    metrics.reset_for_tests()
    op.record_outbound_proxy_error(
        service="bandcamp",
        proxy_url=None,
        method="GET",
        url="https://bandcamp.com/search?q=x",
        error=RuntimeError("network down"),
    )

    snapshot = metrics.snapshot_metrics()
    recent = snapshot["recent_requests"][0]
    assert snapshot["transport_errors"]["bandcamp"] == 1
    assert recent["service"] == "bandcamp"
    assert recent["transport"] == "direct"
    assert recent["error"] == "network down"
    metrics.reset_for_tests()
