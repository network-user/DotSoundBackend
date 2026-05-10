import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.abuse_event import AbuseEvent
from app.services.abuse_fingerprint_adapter import (
    AbuseSignals,
    Decision,
)
from app.services.abuse_signal_service import (
    AbuseSignalService,
)

pytestmark = pytest.mark.anyio


async def test_evaluate_event_persists_and_returns_pass(
    session: AsyncSession,
) -> None:
    svc = AbuseSignalService(session)
    decision = await svc.evaluate_event(
        kind="login",
        ip_masked="10.0.0.0/24",
        signal_hash="hash-a",
        user_id=None,
        signals=AbuseSignals(),
    )
    rows = (
        await session.execute(select(AbuseEvent))
    ).scalars().all()
    assert decision is Decision.PASS
    assert len(rows) == 1
    assert rows[0].kind == "login"
    assert rows[0].score == 0


async def test_evaluate_event_lockout_on_dirty_signals(
    session: AsyncSession,
) -> None:
    svc = AbuseSignalService(session)
    signals = AbuseSignals(
        same_signal_distinct_users=8,
        same_ip_distinct_users=12,
        tor_or_disposable_email=True,
    )
    decision = await svc.evaluate_event(
        kind="register",
        ip_masked="10.0.0.0/24",
        signal_hash="hash-b",
        user_id=None,
        signals=signals,
    )
    assert decision is Decision.LOCKOUT
    rows = (
        await session.execute(select(AbuseEvent))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].score >= 6
