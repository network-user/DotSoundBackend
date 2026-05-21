"""Integration test for the listen_events daily aggregation worker.

The worker uses Postgres-only constructs (``ON CONFLICT DO UPDATE``
with ``EXCLUDED``, ``COUNT(*) FILTER (WHERE ...)``, ``AT TIME ZONE``)
that the default sqlite test backend cannot execute. We require an
opt-in Postgres URL via ``DOTSOUND_TEST_PG_URL`` so the rest of the
suite stays sqlite-friendly.

Run locally:
    DOTSOUND_TEST_PG_URL=postgresql+asyncpg://dotsound:dotsound@\
        localhost:5432/dotsound_test \
        poetry run pytest tests/app/services/test_event_aggregation_worker.py
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.models.base import Base
from app.models.listen_event import ListenEvent
from app.models.listen_event_daily import ListenEventDaily

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        not os.environ.get("DOTSOUND_TEST_PG_URL"),
        reason="needs a Postgres URL via DOTSOUND_TEST_PG_URL",
    ),
]


@pytest.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    url = os.environ["DOTSOUND_TEST_PG_URL"]
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(delete(ListenEvent))
        await conn.execute(delete(ListenEventDaily))
    await engine.dispose()


@pytest.fixture
async def pg_session(
    pg_engine: AsyncEngine,
) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        pg_engine, expire_on_commit=False
    )
    async with factory() as session:
        yield session


async def _seed_events(
    session: AsyncSession,
    *,
    now: datetime,
    days_ago: int,
    user_id: int,
    track_id: int,
    plays: int,
    seconds_per_play: int,
    completed: bool = False,
    skipped: bool = False,
) -> None:
    bucket = now - timedelta(days=days_ago)
    for i in range(plays):
        event = ListenEvent(
            user_id=user_id,
            track_id=track_id,
            started_at=bucket + timedelta(minutes=i),
            duration_listened_seconds=seconds_per_play,
            total_duration_seconds=seconds_per_play + 30,
            last_position_seconds=seconds_per_play,
            completed=completed,
            skipped=skipped,
        )
        event.created_at = bucket + timedelta(minutes=i)
        session.add(event)
    await session.commit()


async def test_aggregation_folds_old_days_and_keeps_recent(
    pg_engine: AsyncEngine,
    pg_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    monkeypatch.setattr(
        "app.services.event_aggregation_worker.AsyncSessionLocal",
        factory,
    )
    monkeypatch.setattr(
        "app.services.event_retention_adapter."
        "listen_event_raw_retention_days",
        lambda: 2,
    )

    now = datetime.now(UTC)
    await _seed_events(
        pg_session,
        now=now,
        days_ago=5,
        user_id=1,
        track_id=10,
        plays=4,
        seconds_per_play=30,
        completed=True,
    )
    await _seed_events(
        pg_session,
        now=now,
        days_ago=5,
        user_id=1,
        track_id=10,
        plays=2,
        seconds_per_play=10,
        skipped=True,
    )
    await _seed_events(
        pg_session,
        now=now,
        days_ago=4,
        user_id=2,
        track_id=20,
        plays=3,
        seconds_per_play=60,
        completed=True,
    )
    await _seed_events(
        pg_session,
        now=now,
        days_ago=1,
        user_id=1,
        track_id=10,
        plays=5,
        seconds_per_play=45,
        completed=True,
    )

    from app.services.event_aggregation_worker import (
        aggregate_listen_events_task,
    )

    summary = await aggregate_listen_events_task()

    assert summary["retention_days"] == 2
    assert summary["days_processed"] == 2
    assert summary["rows_deleted"] == 9

    raw_count = await pg_session.execute(
        select(func.count()).select_from(ListenEvent)
    )
    assert raw_count.scalar_one() == 5

    agg_rows = (
        await pg_session.execute(
            select(
                ListenEventDaily.user_id,
                ListenEventDaily.track_id,
                ListenEventDaily.plays,
                ListenEventDaily.listen_seconds,
                ListenEventDaily.completes,
                ListenEventDaily.skips,
            ).order_by(
                ListenEventDaily.user_id,
                ListenEventDaily.track_id,
            )
        )
    ).all()
    rows_by_pair = {(r[0], r[1]): r[2:] for r in agg_rows}
    assert rows_by_pair[(1, 10)] == (6, 4 * 30 + 2 * 10, 4, 2)
    assert rows_by_pair[(2, 20)] == (3, 3 * 60, 3, 0)


async def test_aggregation_is_idempotent(
    pg_engine: AsyncEngine,
    pg_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    monkeypatch.setattr(
        "app.services.event_aggregation_worker.AsyncSessionLocal",
        factory,
    )
    monkeypatch.setattr(
        "app.services.event_retention_adapter."
        "listen_event_raw_retention_days",
        lambda: 2,
    )

    now = datetime.now(UTC)
    await _seed_events(
        pg_session,
        now=now,
        days_ago=5,
        user_id=1,
        track_id=10,
        plays=4,
        seconds_per_play=30,
        completed=True,
    )

    from app.services.event_aggregation_worker import (
        aggregate_listen_events_task,
    )

    first = await aggregate_listen_events_task()
    second = await aggregate_listen_events_task()

    assert first["rows_deleted"] == 4
    assert second["rows_deleted"] == 0
    assert second["days_processed"] == 0

    agg_row = (
        await pg_session.execute(
            select(
                ListenEventDaily.plays,
                ListenEventDaily.listen_seconds,
                ListenEventDaily.completes,
            ).where(
                ListenEventDaily.user_id == 1,
                ListenEventDaily.track_id == 10,
            )
        )
    ).one()
    assert agg_row == (4, 4 * 30, 4)
