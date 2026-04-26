from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from app.services.tor_pool import (
    _search_tor_bundles,
    resolve_tor_executable,
)


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
