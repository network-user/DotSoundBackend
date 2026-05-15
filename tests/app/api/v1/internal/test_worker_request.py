from __future__ import annotations

from starlette.requests import Request

from app.api.v1.internal.worker_request import client_ip


def _request(peer_ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/internal/audio-compute/jobs/claim",
            "headers": [],
            "client": (peer_ip, 12345),
            "server": ("test", 80),
            "scheme": "http",
        }
    )


def test_client_ip_prefers_internal_allowlist_state() -> None:
    request = _request("172.18.0.9")
    request.state.internal_api_client_ip = "203.0.113.10"

    assert client_ip(request) == "203.0.113.10"
