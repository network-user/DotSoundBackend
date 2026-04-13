from __future__ import annotations

import pytest

import dotsound_private_core.services.abuse as abuse_mod
from app.core.disposable_email import (
    is_disposable_email,
)


def _reset_cache() -> None:
    abuse_mod._DISPOSABLE_DOMAINS = None


@pytest.mark.parametrize(
    "email",
    [
        "test@mailinator.com",
        "foo@yopmail.com",
    ],
)
def test_known_disposable_returns_true(
    email: str,
) -> None:
    _reset_cache()
    assert is_disposable_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "user@gmail.com",
        "user@example.com",
    ],
)
def test_normal_domain_returns_false(
    email: str,
) -> None:
    _reset_cache()
    assert is_disposable_email(email) is False


@pytest.mark.parametrize(
    "email",
    [
        "foo@Mailinator.COM",
        "foo@YOPMAIL.Com",
    ],
)
def test_case_insensitive(email: str) -> None:
    _reset_cache()
    assert is_disposable_email(email) is True


@pytest.mark.parametrize(
    "email,expected",
    [
        ("  foo@mailinator.com  ", True),
        ("  user@gmail.com  ", False),
    ],
)
def test_whitespace_stripped(
    email: str, expected: bool
) -> None:
    _reset_cache()
    assert is_disposable_email(email) is expected


def test_multiple_at_signs_uses_last_part() -> None:
    _reset_cache()
    assert is_disposable_email(
        "bad@@mailinator.com"
    ) is True


def test_empty_string_returns_false() -> None:
    _reset_cache()
    assert is_disposable_email("") is False
