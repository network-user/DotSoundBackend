from __future__ import annotations

import os
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest

from app.services.tor_pool import (
    TorCircuit,
    TorPool,
    _log_outbound_public_ip,
    _resolve_tor_control_port,
    _search_tor_bundles,
    resolve_tor_executable,
)

pytestmark = pytest.mark.anyio


def test_resolve_uses_config_file(
    tmp_path: Path,
) -> None:
    name = "mocks_tor.exe" if os.name == "nt" else "mocks_tor"
    f = tmp_path / name
    f.write_bytes(b"")
    p = f.resolve()
    out = resolve_tor_executable(str(p))
    assert out == str(p)


def test_resolve_uses_shutil_which() -> None:
    with mock.patch("app.services.tor_pool.shutil.which") as w:
        w.return_value = "/opt/homebrew/bin/tor"
        out = resolve_tor_executable("")
    assert out == "/opt/homebrew/bin/tor"


def test_bundle_candidates_not_empty() -> None:
    paths = _search_tor_bundles()
    assert len(paths) > 0
    ex = "tor.exe" if os.name == "nt" else "tor"
    assert all(p.name == ex for p in paths)


def test_control_port_moved_out_of_socks_range() -> None:
    out = _resolve_tor_control_port(9050, 10, 9051)
    assert out == 9060
    out2 = _resolve_tor_control_port(9050, 1, 9051)
    assert out2 == 9051
    out3 = _resolve_tor_control_port(9050, 10, 10000)
    assert out3 == 10000


def test_report_proxy_result_updates_matching_circuit() -> None:
    pool = TorPool(settings=mock.MagicMock())
    pool._circuits = [TorCircuit(index=0, socks_port=9050)]
    url = pool._circuits[0].proxy_url

    pool.report_proxy_result(url, ok=False)
    pool.report_proxy_result(url, ok=True)

    circuit = pool._circuits[0]
    assert circuit.fail_count == 1
    assert circuit.ok_count == 1


def test_describe_proxy_returns_circuit_observability() -> None:
    pool = TorPool(settings=mock.MagicMock())
    pool._circuits = [
        TorCircuit(
            index=2,
            socks_port=9052,
            exit_ip="203.0.113.77",
        )
    ]
    url = pool._circuits[0].proxy_url

    description = pool.describe_proxy(url)

    assert description == {
        "transport": "tor",
        "identity": "tor:c2",
        "egress_ip": "203.0.113.77",
        "socks_port": 9052,
    }


def test_tor_circuit_proxy_url_includes_isolation_credentials() -> None:
    c = TorCircuit(index=3, socks_port=9053)
    url = c.proxy_url
    assert url.startswith("socks5://")
    assert "c3:" in url
    assert "@127.0.0.1:9053" in url


def test_tor_circuit_proxy_url_unique_per_index() -> None:
    c0 = TorCircuit(index=0, socks_port=9050)
    c1 = TorCircuit(index=1, socks_port=9051)
    assert c0.proxy_url != c1.proxy_url


def test_register_newnym_callback_is_called_after_renewal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    def my_cb() -> None:
        called.append("sync")

    pool = TorPool(settings=mock.MagicMock())
    pool.register_newnym_callback(my_cb)
    assert my_cb in pool._newnym_callbacks


async def test_run_newnym_callbacks_calls_sync_and_async() -> None:
    sync_calls: list[int] = []
    async_calls: list[int] = []

    def sync_cb() -> None:
        sync_calls.append(1)

    async def async_cb() -> None:
        async_calls.append(1)

    pool = TorPool(settings=mock.MagicMock())
    pool._newnym_callbacks = [sync_cb, async_cb]
    await pool._run_newnym_callbacks()

    assert sync_calls == [1]
    assert async_calls == [1]


async def test_run_newnym_callbacks_swallows_exceptions() -> None:
    def bad_cb() -> None:
        raise RuntimeError("boom")

    good_calls: list[int] = []

    def good_cb() -> None:
        good_calls.append(1)

    pool = TorPool(settings=mock.MagicMock())
    pool._newnym_callbacks = [bad_cb, good_cb]
    await pool._run_newnym_callbacks()

    assert good_calls == [1]


async def test_force_newnym_skipped_without_controller() -> None:
    pool = TorPool(settings=mock.MagicMock())
    pool._control_port = 0
    pool._controller = None
    ok = await pool.force_newnym(reason="test")
    assert ok is False


async def test_force_newnym_signals_and_runs_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = TorPool(settings=mock.MagicMock())
    pool._circuits = [TorCircuit(index=0, socks_port=9050)]
    controller = mock.MagicMock()
    controller.signal = mock.MagicMock()
    pool._controller = controller
    pool._control_port = 9051

    cb_calls: list[int] = []

    async def cb() -> None:
        cb_calls.append(1)

    pool._newnym_callbacks = [cb]

    fake_signal_module = mock.MagicMock()
    fake_signal_module.NEWNYM = "NEWNYM"
    monkeypatch.setitem(__import__("sys").modules, "stem", fake_signal_module)

    ok = await pool.force_newnym(reason="test", cooldown_s=0.0)

    assert ok is True
    controller.signal.assert_called_once()
    assert cb_calls == [1]
    assert pool._circuits[0].fail_count == 0
    assert pool._circuits[0].ok_count == 0


async def test_force_newnym_throttled_within_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = TorPool(settings=mock.MagicMock())
    pool._circuits = [TorCircuit(index=0, socks_port=9050)]
    controller = mock.MagicMock()
    pool._controller = controller
    pool._control_port = 9051

    fake_signal_module = mock.MagicMock()
    fake_signal_module.NEWNYM = "NEWNYM"
    monkeypatch.setitem(__import__("sys").modules, "stem", fake_signal_module)

    ok1 = await pool.force_newnym(reason="first", cooldown_s=300.0)
    ok2 = await pool.force_newnym(reason="second", cooldown_s=300.0)

    assert ok1 is True
    assert ok2 is False
    controller.signal.assert_called_once()


def test_desktop_tbb_path_in_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name != "nt":
        return
    from pathlib import Path as Pth

    monkeypatch.setattr(
        Pth,
        "home",
        classmethod(lambda _cls: tmp_path),
    )
    paths = _search_tor_bundles()
    want = (
        tmp_path
        / "Desktop"
        / "Tor Browser"
        / "Browser"
        / "TorBrowser"
        / "Tor"
        / "tor.exe"
    )
    assert want in paths


@patch("app.services.tor_pool.httpx.AsyncClient")
async def test_log_outbound_public_ip_uses_ipify(
    client_cls: mock.MagicMock,
) -> None:
    resp = mock.MagicMock()
    resp.text = "203.0.113.1\n"
    resp.raise_for_status = mock.MagicMock()
    inst = client_cls.return_value
    inst.__aenter__ = AsyncMock(return_value=inst)
    inst.__aexit__ = AsyncMock(return_value=None)
    inst.get = AsyncMock(return_value=resp)
    with mock.patch("app.services.tor_pool.logger.info") as logi:
        await _log_outbound_public_ip()
    logi.assert_called_once()
    assert logi.call_args.kwargs["public_ip"] == "203.0.113.1"
