from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.abuse_event import AbuseEvent
from app.repositories.abuse_event import AbuseEventRepository

pytestmark = pytest.mark.anyio


async def _add_event(
    session: AsyncSession,
    *,
    ip: str | None = None,
    sig: str | None = None,
    user_id: int | None = None,
    kind: str = "login",
    score: int = 0,
    minutes_ago: int = 0,
) -> None:
    moment = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    session.add(
        AbuseEvent(
            ip_masked=ip,
            signal_hash=sig,
            user_id=user_id,
            kind=kind,
            score=score,
            created_at=moment,
        )
    )
    await session.flush()


async def test_recent_signal_counts_empty(
    session: AsyncSession,
) -> None:
    repo = AbuseEventRepository(session)
    counts = await repo.recent_signal_counts(
        ip_masked="10.0.0.0/24",
        signal_hash="hash",
    )
    assert counts.ip_hits == 0
    assert counts.same_ip_distinct_users == 0
    assert counts.same_signal_distinct_users == 0


async def test_recent_signal_counts_short_vs_long_window(
    session: AsyncSession,
) -> None:
    repo = AbuseEventRepository(session)
    ip = "10.0.0.0/24"
    # within short window: 3 register events, 0 outside
    for _ in range(3):
        await _add_event(
            session, ip=ip, kind="register", minutes_ago=5
        )
    # outside short window (10 min): should be excluded
    await _add_event(
        session, ip=ip, kind="register", minutes_ago=20
    )

    counts = await repo.recent_signal_counts(
        ip_masked=ip, signal_hash=None
    )
    assert counts.register_burst_from_ip == 3
    # ip_hits uses long window (1h): all 4 visible
    assert counts.ip_hits == 4


async def test_recent_signal_counts_failed_login_burst(
    session: AsyncSession,
) -> None:
    repo = AbuseEventRepository(session)
    ip = "10.0.1.0/24"
    # only events with score >= 3 count as "failed burst"
    await _add_event(
        session, ip=ip, kind="login", score=3, minutes_ago=2
    )
    await _add_event(
        session, ip=ip, kind="login", score=6, minutes_ago=4
    )
    await _add_event(
        session, ip=ip, kind="login", score=0, minutes_ago=1
    )

    counts = await repo.recent_signal_counts(
        ip_masked=ip, signal_hash=None
    )
    assert counts.failed_login_burst == 2


async def test_prune_older_than_removes_old_rows(
    session: AsyncSession,
) -> None:
    repo = AbuseEventRepository(session)
    await _add_event(session, ip="x", minutes_ago=0)
    await _add_event(session, ip="x", minutes_ago=60 * 24 * 31)
    cutoff = datetime.now(UTC) - timedelta(days=30)

    deleted = await repo.prune_older_than(cutoff=cutoff)
    assert deleted == 1
    counts = await repo.recent_signal_counts(
        ip_masked="x", signal_hash=None
    )
    # the recent one is still there
    assert counts.ip_hits == 1
