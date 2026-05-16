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


async def test_enqueue_can_pass_job_id_to_task_payload(
    db_session: AsyncSession,
) -> None:
    captured: dict[str, object] = {}

    class Kicker:
        def with_labels(self, **_labels: str) -> Kicker:
            return self

        async def kiq(self, **payload: object) -> None:
            captured.update(payload)

    class Task:
        task_name = "tests.job_id_task"

        def kicker(self) -> Kicker:
            return Kicker()

    job_id = await background_jobs.enqueue(
        Task(),
        payload={"track_id": 1, "background_job_id": "stale"},
        job_id_payload_key="background_job_id",
        session=db_session,
    )

    row = await db_session.get(BackgroundJob, job_id)
    assert row is not None
    assert captured["track_id"] == 1
    assert captured["background_job_id"] == job_id
    assert row.payload == {"track_id": 1}
