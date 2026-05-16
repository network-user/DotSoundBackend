from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob
from app.models.compute_worker import ComputeWorker
from app.services import compute_job_reaper
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import LocalComputeJob

pytestmark = pytest.mark.anyio


async def _worker(db_session: AsyncSession) -> str:
    wid = "w_reaper_0123456789ab"
    db_session.add(
        ComputeWorker(
            id=wid,
            name=wid,
            profile="cpu_light",
            token_hash="test",
            active=True,
            max_concurrent_jobs=8,
        )
    )
    await db_session.commit()
    return wid


async def _expired_claim(
    db_session: AsyncSession,
    *,
    attempts: int,
) -> ComputeJob:
    wid = await _worker(db_session)
    job = await q.enqueue(
        db_session,
        job_type=q.JOB_SC_ARTIST_CATALOG_SYNC,
        target_kind=q.TARGET_KIND_ARTIST,
        target_id=123,
        payload={"artist_id": 123},
        max_attempts=3,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id=wid,
        job_types=[q.JOB_SC_ARTIST_CATALOG_SYNC],
    )
    assert claimed is not None
    claimed.attempts = attempts
    claimed.claim_deadline_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()
    return job


async def test_reaper_requeues_before_fallback_threshold(
    db_session: AsyncSession,
) -> None:
    job = await _expired_claim(db_session, attempts=1)

    stats = await compute_job_reaper.reap_once(limit=10)

    assert stats["requeued"] == 1
    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None
    assert refreshed.status == q.STATUS_PENDING
    assert refreshed.claimed_by is None
    assert refreshed.last_error == "lease_expired"


async def test_reaper_runs_local_fallback_after_threshold(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = await _expired_claim(db_session, attempts=2)
    seen: list[str] = []

    async def _handler(local_job: LocalComputeJob) -> dict:
        seen.append(local_job.job_type)
        return {"status": "fallback_ok"}

    monkeypatch.setattr(
        compute_job_reaper,
        "get_local_handler",
        lambda _job_type: _handler,
    )

    stats = await compute_job_reaper.reap_once(limit=10)

    assert stats["local_fallback"] == 1
    assert seen == [q.JOB_SC_ARTIST_CATALOG_SYNC]
    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None
    assert refreshed.status == q.STATUS_SUCCEEDED
    assert refreshed.result == {"status": "fallback_ok"}


async def test_dead_track_failure_is_terminal(
    db_session: AsyncSession,
) -> None:
    job = await _expired_claim(db_session, attempts=1)
    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None

    outcome = await compute_job_reaper.handle_worker_failure(
        db_session,
        job=refreshed,
        error_kind="dead_track",
        reason="dead_track",
    )
    await db_session.commit()

    assert outcome == "failed_terminal"
    assert refreshed.status == q.STATUS_FAILED
