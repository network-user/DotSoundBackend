from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.services import compute_worker_service as cws

pytestmark = pytest.mark.anyio


async def test_lyrics_claim_respects_pinned_worker(
    db_session: AsyncSession,
) -> None:
    track = Track(
        title="t",
        artist="a",
        is_active=True,
        is_public=True,
        source="internal",
    )
    db_session.add(track)
    await db_session.flush()
    token_hash = "b" * 64
    w1 = ComputeWorker(
        id="w_claim_a",
        name="a",
        profile="gpu_full",
        token_hash=token_hash,
        active=True,
    )
    w2 = ComputeWorker(
        id="w_claim_b",
        name="b",
        profile="gpu_full",
        token_hash=token_hash,
        active=True,
    )
    db_session.add_all([w1, w2])
    job = LyricsJob(
        id="lj_pin_1",
        track_id=track.id,
        progress_id="prog_pin_1",
        profile="gpu_full",
        status="queued",
        pinned_worker_id="w_claim_b",
        queue_priority=0,
    )
    db_session.add(job)
    await db_session.commit()

    miss = await cws.claim_next_job(
        db_session, worker=w1
    )
    assert miss is None
    hit = await cws.claim_next_job(
        db_session, worker=w2
    )
    assert hit is not None
    assert hit.id == job.id
    await db_session.refresh(job)
    assert job.pinned_worker_id is None


async def test_lyrics_claim_prefers_higher_queue_priority(
    db_session: AsyncSession,
) -> None:
    track = Track(
        title="t2",
        artist="a",
        is_active=True,
        is_public=True,
        source="internal",
    )
    db_session.add(track)
    await db_session.flush()
    token_hash = "c" * 64
    w = ComputeWorker(
        id="w_pri",
        name="p",
        profile="gpu_full",
        token_hash=token_hash,
        active=True,
    )
    db_session.add(w)
    lo = LyricsJob(
        id="lj_lo",
        track_id=track.id,
        progress_id="prog_lo",
        profile="gpu_full",
        status="queued",
        queue_priority=0,
    )
    hi = LyricsJob(
        id="lj_hi",
        track_id=track.id,
        progress_id="prog_hi",
        profile="gpu_full",
        status="queued",
        queue_priority=50,
    )
    db_session.add_all([lo, hi])
    await db_session.commit()

    claimed = await cws.claim_next_job(
        db_session, worker=w
    )
    assert claimed is not None
    assert claimed.id == "lj_hi"


async def test_empty_claim_diagnostic_reports_profile_mismatch(
    db_session: AsyncSession,
) -> None:
    track = Track(
        title="t3",
        artist="a",
        is_active=True,
        is_public=True,
        source="internal",
    )
    worker = ComputeWorker(
        id="w_diag_cpu",
        name="diag",
        profile="cpu_light",
        token_hash="d" * 64,
        active=True,
    )
    job = LyricsJob(
        id="lj_diag_gpu",
        track_id=1,
        progress_id="prog_diag_gpu",
        profile="gpu_full",
        status="queued",
        queue_priority=0,
    )
    db_session.add(track)
    await db_session.flush()
    job.track_id = track.id
    db_session.add_all([worker, job])
    await db_session.commit()

    meta = await cws.diagnose_empty_lyrics_claim(
        db_session,
        worker=worker,
    )

    assert meta["reason"] == "profile_mismatch"
    assert meta["claim_profiles"] == ["cpu_light"]
    assert meta["queued_profiles"] == {"gpu_full": 1}


async def test_empty_claim_diagnostic_reports_capacity(
    db_session: AsyncSession,
) -> None:
    track = Track(
        title="t4",
        artist="a",
        is_active=True,
        is_public=True,
        source="internal",
    )
    worker = ComputeWorker(
        id="w_diag_capacity",
        name="diag-capacity",
        profile="gpu_full",
        token_hash="e" * 64,
        active=True,
        max_concurrent_jobs=1,
    )
    running = LyricsJob(
        id="lj_diag_running",
        track_id=1,
        progress_id="prog_diag_running",
        profile="gpu_full",
        status="running",
        routed_to_worker=worker.id,
        queue_priority=0,
    )
    queued = LyricsJob(
        id="lj_diag_queued",
        track_id=1,
        progress_id="prog_diag_queued",
        profile="gpu_full",
        status="queued",
        queue_priority=0,
    )
    db_session.add(track)
    await db_session.flush()
    running.track_id = track.id
    queued.track_id = track.id
    db_session.add_all([worker, running, queued])
    await db_session.commit()

    meta = await cws.diagnose_empty_lyrics_claim(
        db_session,
        worker=worker,
    )

    assert meta["reason"] == "worker_at_capacity"
    assert meta["in_flight"] == 1
    assert meta["max_concurrent_jobs"] == 1


async def test_empty_claim_diagnostic_reports_pinned_elsewhere(
    db_session: AsyncSession,
) -> None:
    track = Track(
        title="t5",
        artist="a",
        is_active=True,
        is_public=True,
        source="internal",
    )
    worker = ComputeWorker(
        id="w_diag_pin_a",
        name="diag-pin-a",
        profile="gpu_full",
        token_hash="f" * 64,
        active=True,
    )
    other = ComputeWorker(
        id="w_diag_pin_b",
        name="diag-pin-b",
        profile="gpu_full",
        token_hash="f" * 64,
        active=True,
    )
    job = LyricsJob(
        id="lj_diag_pinned",
        track_id=1,
        progress_id="prog_diag_pinned",
        profile="gpu_full",
        status="queued",
        pinned_worker_id=other.id,
        queue_priority=0,
    )
    db_session.add(track)
    await db_session.flush()
    job.track_id = track.id
    db_session.add_all([worker, other, job])
    await db_session.commit()

    meta = await cws.diagnose_empty_lyrics_claim(
        db_session,
        worker=worker,
    )

    assert meta["reason"] == "jobs_pinned_to_other_workers"
    assert meta["queued_matching_profiles"] == 1
    assert meta["queued_claimable"] == 0
    assert meta["queued_pinned_elsewhere"] == 1
