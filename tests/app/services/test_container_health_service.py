from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.services import container_health_service as svc


def test_collect_sync_closes_docker_client_on_list_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Containers:
        def list(self, *, all: bool) -> list[object]:
            raise RuntimeError("socket failed")

    class _Client:
        closed = False
        containers = _Containers()

        def close(self) -> None:
            type(self).closed = True

    fake_docker = SimpleNamespace(
        DockerClient=lambda base_url: _Client(),
    )
    monkeypatch.setitem(sys.modules, "docker", fake_docker)

    assert svc._collect_sync() == []
    assert _Client.closed is True
