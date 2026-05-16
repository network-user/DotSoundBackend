from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import BackgroundJob
from app.services import background_jobs

pytestmark = pytest.mark.anyio


class _FakeKicker:
    def with_labels(self, **_labels: str) -> _FakeKicker:
        return self

    async def kiq(self, **_payload: object) -> None:
        return None


class _FakeTask:
    task_name = "tests.repair_track_playback_task"

    def kicker(self) -> _FakeKicker:
        return _FakeKicker()


async def test_enqueue_allows_reused_idempotency_key_after_guard_window(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _slot_open(_key: str, *, ttl_seconds: int) -> bool:
        return True

    monkeypatch.setattr(
        background_jobs,
        "acquire_idempotency_slot",
        _slot_open,
    )

    first_id = await background_jobs.enqueue(
        _FakeTask(),
        payload={"track_id": 1},
        idempotency_key="playback-repair:track:1",
        session=db_session,
    )
    second_id = await background_jobs.enqueue(
        _FakeTask(),
        payload={"track_id": 1},
        idempotency_key="playback-repair:track:1",
        session=db_session,
    )

    rows = (
        await db_session.scalars(
            select(BackgroundJob).where(
                BackgroundJob.idempotency_key
                == "playback-repair:track:1"
            )
        )
    ).all()

    assert first_id != second_id
    assert len(rows) == 2
