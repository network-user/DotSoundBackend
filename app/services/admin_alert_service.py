"""Admin alert dispatcher.

Sends alerts about critical admin events to a Telegram chat
through DotSoundBot's internal HTTP endpoint. The decision
whether to alert at all is delegated to PrivateCore via
``should_alert_on_event``. The bot endpoint contract is documented
in ``docs/admin/security.md``.

Backend ↔ Bot contract::

    POST {bot_internal_url}/internal/admin-alert
    Headers:
      X-Internal-Secret: {bot_internal_secret}
      Content-Type: application/json
    Body:
      {
        "chat_id": "<ADMIN_TELEGRAM_ALERT_CHAT_ID>",
        "event_type": "...",
        "severity": "info" | "warning" | "critical",
        "title": "...",
        "details": "...",
        "user_id": int | null,
        "ip": str | null,
        "ua": str | null,
        "ts": ISO8601
      }

The bot is expected to forward this as a Markdown message to the
chat. Backend never knows or stores the chat token.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from dotsound_private_core.services.admin_security_policy import (
    should_alert_on_event,
)
from dotsound_private_core.services.internal_bridge import (
    admin_alert_url,
    build_internal_headers,
)

from app.config import settings
from app.core.tkq import broker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _format_payload(
    *,
    event_type: str,
    severity: str,
    title: str,
    details: str,
    user_id: int | None,
    ip: str | None,
    ua: str | None,
) -> dict[str, Any]:
    return {
        "chat_id": (settings.admin_telegram_alert_chat_id or None),
        "event_type": event_type,
        "severity": severity,
        "title": title,
        "details": details,
        "user_id": user_id,
        "ip": ip,
        "ua": ua,
        "ts": datetime.now(UTC).isoformat(),
    }


@broker.task(task_name="admin.alert.send")
async def send_admin_alert_task(
    event_type: str,
    severity: str,
    title: str,
    details: str,
    user_id: int | None = None,
    ip: str | None = None,
    ua: str | None = None,
) -> None:
    if not should_alert_on_event(event_type, severity):
        return
    if (
        not settings.bot_internal_url
        or not settings.bot_internal_secret
        or not settings.admin_telegram_alert_chat_id
    ):
        logger.info(
            "admin_alert_skipped_no_bot_config",
            event_type=event_type,
            severity=severity,
        )
        return

    payload = _format_payload(
        event_type=event_type,
        severity=severity,
        title=title,
        details=details,
        user_id=user_id,
        ip=ip,
        ua=ua,
    )
    url = admin_alert_url(settings.bot_internal_url)
    headers = {
        **build_internal_headers(settings.bot_internal_secret),
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        logger.info(
            "admin_alert_sent",
            event_type=event_type,
            severity=severity,
        )
    except Exception:
        logger.exception(
            "admin_alert_failed",
            event_type=event_type,
            severity=severity,
        )


async def dispatch_alert(
    *,
    event_type: str,
    severity: str,
    title: str,
    details: str,
    user_id: int | None = None,
    ip: str | None = None,
    ua: str | None = None,
) -> None:
    """Enqueue an admin alert through Taskiq.

    Wraps ``send_admin_alert_task.kiq`` so call-sites do not need to
    import Taskiq directly. Raises nothing — alert delivery is best
    effort.
    """
    try:
        await send_admin_alert_task.kiq(
            event_type,
            severity,
            title,
            details,
            user_id,
            ip,
            ua,
        )
    except Exception:
        logger.exception(
            "admin_alert_enqueue_failed",
            event_type=event_type,
            severity=severity,
        )
