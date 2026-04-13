from __future__ import annotations

_DISPOSABLE_DOMAINS: set[str] | None = None


def _load_domains() -> set[str]:
    global _DISPOSABLE_DOMAINS
    if _DISPOSABLE_DOMAINS is not None:
        return _DISPOSABLE_DOMAINS

    try:
        from disposable_email_domains import (  # type: ignore[import-untyped]
            blocklist,
        )

        _DISPOSABLE_DOMAINS = set(blocklist)
    except ImportError:
        _DISPOSABLE_DOMAINS = {
            "mailinator.com",
            "guerrillamail.com",
            "tempmail.com",
            "throwaway.email",
            "yopmail.com",
            "sharklasers.com",
            "guerrillamailblock.com",
            "grr.la",
            "dispostable.com",
            "trashmail.com",
            "tempail.com",
            "fakeinbox.com",
            "10minutemail.com",
            "temp-mail.org",
            "getnada.com",
        }
    return _DISPOSABLE_DOMAINS


def is_disposable_email(email: str) -> bool:
    domain = email.lower().strip().split("@")[-1]
    return domain in _load_domains()
