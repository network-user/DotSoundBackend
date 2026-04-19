from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.admin_alert_service import (
    _format_payload,
    send_admin_alert_task,
)

pytestmark = pytest.mark.anyio


def test_format_payload_includes_required_fields() -> None:
    payload = _format_payload(
        event_type="lockout",
        severity="critical",
        title="Locked",
        details="user 1",
        user_id=1,
        ip="127.0.0.1",
        ua="ua",
    )
    assert payload["event_type"] == "lockout"
    assert payload["severity"] == "critical"
    assert payload["user_id"] == 1
    assert "ts" in payload


async def test_alert_skipped_when_decision_says_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.admin_alert_service.should_alert_on_event",
        lambda *_a, **_k: False,
    )
    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
    ) as mock_post:
        await send_admin_alert_task(
            event_type="x",
            severity="info",
            title="t",
            details="d",
        )
    assert mock_post.call_count == 0


async def test_alert_skipped_when_no_bot_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.admin_alert_service.should_alert_on_event",
        lambda *_a, **_k: True,
    )

    class _Cfg:
        bot_internal_url = ""
        bot_internal_secret = ""
        admin_telegram_alert_chat_id = ""

    monkeypatch.setattr(
        "app.services.admin_alert_service.settings",
        _Cfg(),
    )
    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
    ) as mock_post:
        await send_admin_alert_task(
            event_type="x",
            severity="critical",
            title="t",
            details="d",
        )
    assert mock_post.call_count == 0
