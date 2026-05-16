from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob
from app.services import compute_job_dispatcher as dispatcher
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import LocalComputeJob

pytestmark = pytest.mark.anyio


async def test_dispatch_runs_local_when_offload_disabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dispatcher.settings, "compute_offload_enabled", False)

    async def _handler(job: LocalComputeJob) -> dict:
        return {"status": "local_ok", "artist_id": int(job.target_id or 0)}

    result = await dispatcher.dispatch_compute_job(
        db_session,
        job_type=q.JOB_SC_ARTIST_CATALOG_SYNC,
        target_kind=q.TARGET_KIND_ARTIST,
        target_id=42,
        payload={"artist_id": 42},
        local_handler=_handler,
    )

    rows = (await db_session.execute(select(ComputeJob))).scalars().all()
    assert result.status == "local"
    assert result.result == {"status": "local_ok", "artist_id": 42}
    assert rows == []


async def test_dispatch_enqueues_when_offload_enabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dispatcher.settings, "compute_offload_enabled", True)

    async def _handler(job: LocalComputeJob) -> dict:
        raise AssertionError("local handler must not run")

    result = await dispatcher.dispatch_compute_job(
        db_session,
        job_type=q.JOB_SC_ARTIST_CATALOG_SYNC,
        target_kind=q.TARGET_KIND_ARTIST,
        target_id=77,
        payload={"artist_id": 77},
        local_handler=_handler,
    )
    await db_session.commit()

    assert result.status == "queued"
    assert result.job_id is not None
    job = await db_session.get(ComputeJob, result.job_id)
    assert job is not None
    assert job.job_type == q.JOB_SC_ARTIST_CATALOG_SYNC
    assert job.target_id == "77"
    assert job.priority == q.default_priority(q.JOB_SC_ARTIST_CATALOG_SYNC)
    assert job.max_attempts == q.default_max_attempts(
        q.JOB_SC_ARTIST_CATALOG_SYNC
    )
