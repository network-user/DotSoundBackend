from unittest.mock import patch

import pytest

from app.core.logging import (
    _mask_value,
    _redact_processor,
    configure_logging,
)

pytestmark = pytest.mark.anyio


def test_mask_value_correlation_passthrough_when_flag_off() -> None:
    with (
        patch("app.core.logging._REDACT_ENABLED", True),
        patch("app.core.logging._REDACT_IDENTIFIERS", False),
    ):
        assert _mask_value("user_id", 42) == 42
        assert _mask_value("public_ip", "203.0.113.1") == "203.0.113.1"


def test_public_ip_partial_mask_when_identifiers_on() -> None:
    with (
        patch("app.core.logging._REDACT_ENABLED", True),
        patch("app.core.logging._REDACT_IDENTIFIERS", True),
    ):
        r = _mask_value("public_ip", "203.0.113.1")
        assert r != "203.0.113.1"
        assert "***" in r


def test_mask_value_email_still_partial_when_ids_off() -> None:
    with (
        patch("app.core.logging._REDACT_ENABLED", True),
        patch("app.core.logging._REDACT_IDENTIFIERS", False),
    ):
        r = _mask_value("email", "someone@example.com")
        assert "@" not in r or "***" in r


def test_redact_url_relaxed_length() -> None:
    with (
        patch("app.core.logging._REDACT_ENABLED", True),
        patch("app.core.logging._REDACT_IDENTIFIERS", False),
    ):
        long_q = "https://x.test/a?k=" + "b" * 100
        out = _redact_processor(
            None,
            "info",
            {"u": long_q},
        )
        assert out["u"] == long_q


def test_configure_sets_identifier_flag() -> None:
    import app.core.logging as mlog

    configure_logging(
        "INFO",
        redact=True,
        redact_identifiers=False,
        json_output=True,
    )
    assert mlog._REDACT_ENABLED is True
    assert mlog._REDACT_IDENTIFIERS is False
    configure_logging(
        "INFO",
        redact=True,
        redact_identifiers=True,
        json_output=True,
    )
    assert mlog._REDACT_ENABLED is True
    assert mlog._REDACT_IDENTIFIERS is True
