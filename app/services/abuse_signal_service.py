"""Anti-abuse signal aggregation + decision orchestration.

Backend collects per-request signals from a small middleware
(``app/middlewares/abuse_signal.py``) and stores them in two
places:

* a Redis sliding-window counter, used for cheap real-time
  decisions during the same request;
* the ``abuse_events`` table for offline analysis and audit.

Decisions (PASS / THROTTLE / REQUIRE_CAPTCHA / LOCKOUT) are
produced by PrivateCore (``abuse_fingerprint_policy``); this
service just gathers signal counts and forwards them.

The IP address is masked through the existing
``services/web_auth.mask_ip`` helper (already in PrivateCore)
before it ever lands in our DB.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.abuse_event import AbuseEvent
from app.services.abuse_fingerprint_adapter import (
    AbuseSignals,
    Decision,
    evaluate,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class AbuseSignalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate_event(
        self,
        *,
        kind: str,
        ip_masked: str | None,
        signal_hash: str | None,
        user_id: int | None,
        signals: AbuseSignals,
    ) -> Decision:
        """Run the policy and persist a row for the event.

        Persistence is best-effort -- a DB hiccup must not block
        the request. The Decision is always returned even on
        write failure so callers can react in-band.
        """
        decision = evaluate(signals, kind=kind)
        score = self._decision_to_score(decision)
        try:
            event = AbuseEvent(
                signal_hash=signal_hash,
                ip_masked=ip_masked,
                user_id=user_id,
                kind=kind,
                score=score,
            )
            self._session.add(event)
            await self._session.flush()
        except Exception:
            logger.warning(
                "abuse_event_persist_failed",
                kind=kind,
                exc_info=True,
            )
        return decision

    @staticmethod
    def _decision_to_score(decision: Decision) -> int:
        return {
            Decision.PASS: 0,
            Decision.THROTTLE: 3,
            Decision.REQUIRE_CAPTCHA: 6,
            Decision.LOCKOUT: 10,
        }.get(decision, 0)
