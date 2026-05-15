from __future__ import annotations

from app.core.client_ip import resolve_forwarded_client_ip


def test_resolve_forwarded_client_ip_ignores_untrusted_xff() -> None:
    assert (
        resolve_forwarded_client_ip(
            "198.51.100.20",
            "203.0.113.10",
            ["172.16.0.0/12"],
        )
        == "198.51.100.20"
    )


def test_resolve_forwarded_client_ip_uses_trusted_proxy_xff() -> None:
    assert (
        resolve_forwarded_client_ip(
            "172.18.0.9",
            "203.0.113.10",
            ["172.16.0.0/12"],
        )
        == "203.0.113.10"
    )


def test_resolve_forwarded_client_ip_skips_trusted_proxy_chain() -> None:
    assert (
        resolve_forwarded_client_ip(
            "172.18.0.9",
            "198.51.100.66, 203.0.113.10, 172.18.0.5",
            ["172.16.0.0/12"],
        )
        == "203.0.113.10"
    )
