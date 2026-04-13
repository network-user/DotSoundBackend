from __future__ import annotations

import dotsound_private_core.services.abuse as abuse_mod
from app.core.disposable_email import (
    is_disposable_email,
)


def _reset_cache() -> None:
    abuse_mod._DISPOSABLE_DOMAINS = None


def test_known_disposable_returns_true() -> None:
    _reset_cache()

    assert is_disposable_email(
        "test@mailinator.com"
    ) is True
    assert is_disposable_email(
        "foo@yopmail.com"
    ) is True


def test_normal_domain_returns_false() -> None:
    _reset_cache()

    assert is_disposable_email(
        "user@gmail.com"
    ) is False
    assert is_disposable_email(
        "user@example.com"
    ) is False


def test_case_insensitive() -> None:
    _reset_cache()

    assert is_disposable_email(
        "foo@Mailinator.COM"
    ) is True
    assert is_disposable_email(
        "foo@YOPMAIL.Com"
    ) is True


def test_whitespace_stripped() -> None:
    _reset_cache()

    assert is_disposable_email(
        "  foo@mailinator.com  "
    ) is True
    assert is_disposable_email(
        "  user@gmail.com  "
    ) is False


def test_multiple_at_signs_uses_last_part() -> None:
    _reset_cache()

    assert is_disposable_email(
        "bad@@mailinator.com"
    ) is True


def test_empty_string_returns_false() -> None:
    _reset_cache()

    assert is_disposable_email("") is False
