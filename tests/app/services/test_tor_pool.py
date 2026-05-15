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

    pool.report_proxy_result("socks5://127.0.0.1:9050", ok=False)
    pool.report_proxy_result("socks5://127.0.0.1:9050", ok=True)

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

    description = pool.describe_proxy("socks5://127.0.0.1:9052")

    assert description == {
        "transport": "tor",
        "identity": "tor:c2",
        "egress_ip": "203.0.113.77",
        "socks_port": 9052,
    }


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
