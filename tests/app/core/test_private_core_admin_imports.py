"""Smoke test: backend modules import admin policy from PrivateCore.

This guarantees that the temporary stub at
``app/core/_admin_security_constants.py`` is fully removed and every
admin-flow consumer pulls constants from PrivateCore. Detailed unit
tests for these constants/functions live in PrivateCore itself
(``tests/dotsound_private_core/services/test_admin_security_policy.py``).
"""

from __future__ import annotations

import pytest
from dotsound_private_core.services.admin_security_policy import (
    ADMIN_BACKUP_CODES_COUNT,
    ADMIN_LOGIN_MAX_ATTEMPTS,
    ADMIN_SESSION_TTL_SECONDS,
    ADMIN_STEP_UP_TTL_SECONDS,
    is_step_up_required,
    should_lockout_admin,
)


def test_constants_present() -> None:
    assert ADMIN_SESSION_TTL_SECONDS > 0
    assert ADMIN_BACKUP_CODES_COUNT == 10
    assert ADMIN_LOGIN_MAX_ATTEMPTS > 0
    assert ADMIN_STEP_UP_TTL_SECONDS > 0


def test_decisions_callable() -> None:
    assert should_lockout_admin(ADMIN_LOGIN_MAX_ATTEMPTS) is True
    assert is_step_up_required("users.ban") is True
    assert is_step_up_required("dashboard.view") is False


def test_backend_consumers_import_from_private_core() -> None:
    """Every backend module that previously imported the stub must
    now resolve constants from the PrivateCore policy module.
    """
    from app.api.v1.admin import ws as ws_module
    from app.core import observability as obs_module
    from app.services import (
        admin_alert_service,
        admin_auth_service,
        admin_device_service,
        admin_manifest_service,
    )

    for module in (
        admin_auth_service,
        admin_device_service,
        admin_alert_service,
        admin_manifest_service,
        ws_module,
        obs_module,
    ):
        source = __import__(
            module.__name__,
            fromlist=["__file__"],
        ).__file__
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
        assert "_admin_security_constants" not in text, (
            f"{module.__name__} still imports the "
            "removed stub _admin_security_constants"
        )


def test_temporary_stub_is_gone() -> None:
    with pytest.raises(ImportError):
        __import__("app.core._admin_security_constants")
