"""High-level helper for ``api/v1/auth`` to call the anti-abuse guard.

Wraps the request-side bookkeeping (read X-DS-Signal from
``request.state``, mask the client IP, query the sliding window
in ``abuse_events``, optionally consult Tor list) and returns
the PrivateCore-side ``Decision``. If the decision blocks the
caller, this helper raises ``HTTPException`` directly so the
auth route stays linear.
"""

from __future__ import annotations

import structlog
from dotsound_private_core.services.web_auth import mask_ip
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.abuse_event import AbuseEventRepository
from app.services.abuse_fingerprint_adapter import (
    AbuseSignals,
    Decision,
    evaluate,
)
from app.services.abuse_signal_service import (
    AbuseSignalService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


async def _is_tor(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        from app.core.tor_checker import is_tor_exit_node

        return await is_tor_exit_node(ip)
    except Exception:
        return False


async def evaluate_auth_event(
    request: Request,
    *,
    session: AsyncSession,
    kind: str,
    user_id: int | None,
    is_disposable_email: bool = False,
) -> Decision:
    """Compute and persist a decision for an auth-related event.

    Raises:
        HTTPException(423): on ``Decision.LOCKOUT``.
        HTTPException(429): on ``Decision.REQUIRE_CAPTCHA``.

    Returns the raw Decision otherwise so the caller can decide
    whether to log a soft warning.
    """
    signal_hash: str | None = getattr(
        request.state, "abuse_signal", None
    )
    raw_ip = _client_ip(request)
    ip_masked = mask_ip(raw_ip) if raw_ip else None
    is_new_device = signal_hash is None

    repo = AbuseEventRepository(session)
    counts = await repo.recent_signal_counts(
        ip_masked=ip_masked,
        signal_hash=signal_hash,
    )
    tor_or_disposable = (
        is_disposable_email or await _is_tor(raw_ip)
    )
    signals = AbuseSignals(
        ip_hits=counts.ip_hits,
        same_ip_distinct_users=counts.same_ip_distinct_users,
        same_signal_distinct_users=(
            counts.same_signal_distinct_users
        ),
        failed_login_burst=counts.failed_login_burst,
        register_burst_from_ip=counts.register_burst_from_ip,
        tor_or_disposable_email=tor_or_disposable,
        is_new_device=is_new_device,
    )

    pre = evaluate(signals, kind=kind)
    svc = AbuseSignalService(session)
    decision = await svc.evaluate_event(
        kind=kind,
        ip_masked=ip_masked,
        signal_hash=signal_hash,
        user_id=user_id,
        signals=signals,
    )
    final = pre if decision is Decision.PASS else decision

    if final is Decision.LOCKOUT:
        logger.warning(
            "abuse_guard_lockout",
            kind=kind,
            user_id=user_id,
            ip_masked=ip_masked,
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                "Temporarily blocked due to suspicious "
                "activity. Try again later."
            ),
        )
    if final is Decision.REQUIRE_CAPTCHA:
        logger.info(
            "abuse_guard_captcha",
            kind=kind,
            user_id=user_id,
            ip_masked=ip_masked,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="captcha_required",
        )
    return final
