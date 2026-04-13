from __future__ import annotations

import structlog

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


async def send_magic_link(
    to_email: str, magic_link_url: str
) -> None:
    import resend

    resend.api_key = settings.resend_api_key

    html = (
        "<div style='font-family:sans-serif;"
        "max-width:480px;margin:0 auto;'>"
        "<h2>Sign in to DotSound</h2>"
        "<p>Click the button below to sign in. "
        "This link expires in "
        f"{settings.magic_link_ttl_minutes} minutes.</p>"
        "<a href='" + magic_link_url + "' "
        "style='display:inline-block;padding:12px 32px;"
        "background:#000;color:#fff;"
        "text-decoration:none;border-radius:6px;"
        "font-weight:600;'>Sign in</a>"
        "<p style='margin-top:24px;font-size:13px;"
        "color:#666;'>If the button does not work, "
        "copy and paste this link:<br>"
        "<a href='" + magic_link_url + "'>"
        + magic_link_url + "</a></p>"
        "<hr style='margin-top:32px;border:none;"
        "border-top:1px solid #eee;'>"
        "<p style='font-size:12px;color:#999;'>"
        "If you did not request this, "
        "ignore this email.</p>"
        "</div>"
    )

    params: resend.Emails.SendParams = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Sign in to DotSound",
        "html": html,
    }

    try:
        resend.Emails.send(params)
        logger.info(
            "magic_link_email_sent", to=to_email
        )
    except Exception:
        logger.exception(
            "magic_link_email_failed", to=to_email
        )
        raise


async def send_totp_fallback_code(
    to_email: str, code: str
) -> None:
    import resend

    resend.api_key = settings.resend_api_key

    html = (
        "<div style='font-family:sans-serif;"
        "max-width:480px;margin:0 auto;'>"
        "<h2>Your verification code</h2>"
        "<p>Use this code to complete sign-in:</p>"
        "<div style='font-size:32px;font-weight:700;"
        "letter-spacing:8px;padding:16px 0;'>"
        + code
        + "</div>"
        "<p>This code expires in 5 minutes.</p>"
        "<hr style='margin-top:32px;border:none;"
        "border-top:1px solid #eee;'>"
        "<p style='font-size:12px;color:#999;'>"
        "If you did not request this, "
        "someone may be trying to access your account."
        "</p></div>"
    )

    params: resend.Emails.SendParams = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "DotSound verification code",
        "html": html,
    }

    try:
        resend.Emails.send(params)
        logger.info(
            "totp_fallback_email_sent", to=to_email
        )
    except Exception:
        logger.exception(
            "totp_fallback_email_failed", to=to_email
        )
        raise
