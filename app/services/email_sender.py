from __future__ import annotations

import asyncio
import functools

import structlog
from dotsound_private_core.services.auth_policy import (
    FALLBACK_CODE_TTL,
)

from app.config import settings

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


def _send_sync(
    params: dict[str, object],
) -> None:
    import resend

    resend.api_key = settings.resend_api_key
    resend.Emails.send(params)  # type: ignore[arg-type]


async def _send_async(
    params: dict[str, object],
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        functools.partial(_send_sync, params),
    )


async def send_magic_link(
    to_email: str, magic_link_url: str
) -> None:
    html = (
        "<div style='font-family:sans-serif;"
        "max-width:480px;margin:0 auto;'>"
        "<h2>Sign in to DotSound</h2>"
        "<p>Click the button below to sign in. "
        "This link expires in "
        f"{settings.magic_link_ttl_minutes}"
        " minutes.</p>"
        "<a href='" + magic_link_url + "' "
        "style='display:inline-block;"
        "padding:12px 32px;"
        "background:#000;color:#fff;"
        "text-decoration:none;"
        "border-radius:6px;"
        "font-weight:600;'>Sign in</a>"
        "<p style='margin-top:24px;"
        "font-size:13px;"
        "color:#666;'>If the button "
        "does not work, "
        "copy and paste this link:<br>"
        "<a href='"
        + magic_link_url
        + "'>"
        + magic_link_url
        + "</a></p>"
        "<hr style='margin-top:32px;"
        "border:none;"
        "border-top:1px solid #eee;'>"
        "<p style='font-size:12px;color:#999;'>"
        "If you did not request this, "
        "ignore this email.</p>"
        "</div>"
    )

    params: dict[str, object] = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Sign in to DotSound",
        "html": html,
    }

    try:
        await _send_async(params)
        logger.info(
            "magic_link_email_sent",
            to=to_email,
        )
    except Exception:
        logger.exception(
            "magic_link_email_failed",
            to=to_email,
        )
        raise


async def send_totp_fallback_code(
    to_email: str, code: str
) -> None:
    mid = len(code) // 2
    display_code = f"{code[:mid]} {code[mid:]}"
    if FALLBACK_CODE_TTL % 60 == 0:
        ttl_text = (
            f"{FALLBACK_CODE_TTL // 60} minutes"
        )
    else:
        ttl_text = f"{FALLBACK_CODE_TTL} seconds"
    html = (
        "<div style='font-family:sans-serif;"
        "max-width:480px;margin:0 auto;'>"
        "<h2>Your verification code</h2>"
        "<p>Use this code to complete "
        "sign-in:</p>"
        "<div style='font-size:32px;"
        "font-weight:700;"
        "letter-spacing:6px;"
        "padding:16px 0;'>"
        + display_code
        + "</div>"
        "<p>This code expires in "
        + ttl_text
        + ".</p>"
        "<hr style='margin-top:32px;"
        "border:none;"
        "border-top:1px solid #eee;'>"
        "<p style='font-size:12px;color:#999;'>"
        "If you did not request this, "
        "someone may be trying to "
        "access your account."
        "</p></div>"
    )

    params: dict[str, object] = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "DotSound verification code",
        "html": html,
    }

    try:
        await _send_async(params)
        logger.info(
            "totp_fallback_email_sent",
            to=to_email,
        )
    except Exception:
        logger.exception(
            "totp_fallback_email_failed",
            to=to_email,
        )
        raise
