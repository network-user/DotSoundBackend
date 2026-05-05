from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q

pytestmark = pytest.mark.anyio


async def test_enqueue_is_idempotent(db_session):
    j1 = await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=42,
        feature_version="v1",
        payload={"file_key": "abc"},
    )
    j2 = await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=42,
        feature_version="v1",
        payload={"file_key": "different"},
    )
    assert j1.id == j2.id
    # original payload preserved — duplicate enqueue is a pure no-op
    assert j1.payload == {"file_key": "abc"}
    assert j1.target_id == "42"


async def test_enqueue_different_versions_are_separate_jobs(
    db_session,
):
    j1 = await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=42,
        feature_version="v1",
    )
    j2 = await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=42,
        feature_version="v2",
    )
    assert j1.id != j2.id


async def test_claim_returns_pending_job(db_session):
    job = await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=1,
    )
    await db_session.commit()

    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["track_audio_features"],
    )
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == q.STATUS_CLAIMED
    assert claimed.claimed_by == "w_x"
    assert claimed.attempts == 1
    assert claimed.claim_deadline_at is not None


async def test_claim_skips_other_job_types(db_session):
    await q.enqueue(
        db_session,
        job_type="artist_features_update",
        target_kind="artist",
        target_id=1,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["track_audio_features"],
    )
    assert claimed is None


async def test_claim_returns_none_when_empty(db_session):
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["track_audio_features"],
    )
    assert claimed is None


async def test_claim_respects_pinned_worker(db_session):
    job = await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=901,
    )
    job.pinned_worker_id = "w_b_only"
    await db_session.commit()

    wrong = await q.claim_next(
        db_session,
        worker_id="w_a",
        job_types=["track_audio_features"],
    )
    assert wrong is None

    ok = await q.claim_next(
        db_session,
        worker_id="w_b_only",
        job_types=["track_audio_features"],
    )
    assert ok is not None
    assert ok.id == job.id
    assert ok.pinned_worker_id is None


async def test_claim_respects_priority(db_session):
    low = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
        priority=0,
    )
    high = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=2,
        priority=10,
    )
    await db_session.commit()

    first = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert first is not None
    assert first.id == high.id

    await db_session.commit()
    second = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert second is not None
    assert second.id == low.id


async def test_claim_respects_next_attempt_at(db_session):
    await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
        delay_seconds=300,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is None


async def test_mark_succeeded_is_terminal(db_session):
    job = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None

    await q.mark_succeeded(
        db_session,
        job=claimed,
        result={"feature_version": "v1", "vector_dim": 256},
    )
    await db_session.commit()

    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None
    assert refreshed.status == q.STATUS_SUCCEEDED
    assert refreshed.result is not None
    assert refreshed.result["vector_dim"] == 256
    assert refreshed.finished_at is not None


async def test_mark_failed_retries_with_backoff(db_session):
    job = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
        max_attempts=3,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None
    assert claimed.attempts == 1

    await q.mark_failed(
        db_session,
        job=claimed,
        reason="transient_io_error",
    )
    await db_session.commit()

    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None
    assert refreshed.status == q.STATUS_PENDING
    assert refreshed.last_error == "transient_io_error"
    assert refreshed.claimed_by is None
    # backoff bumps next_attempt_at into the future
    next_at = refreshed.next_attempt_at
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=UTC)
    assert next_at > datetime.now(UTC)


async def test_mark_failed_terminal_after_max_attempts(
    db_session,
):
    job = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
        max_attempts=2,
    )
    await db_session.commit()

    # attempt 1: claim + fail (retry)
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None
    await q.mark_failed(
        db_session, job=claimed, reason="boom"
    )
    await db_session.commit()

    # bypass backoff so the next claim is eligible
    await db_session.refresh(claimed)
    claimed.next_attempt_at = datetime.now(UTC)
    await db_session.commit()

    # attempt 2: claim + fail (terminal)
    claimed2 = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed2 is not None
    assert claimed2.attempts == 2
    await q.mark_failed(
        db_session, job=claimed2, reason="boom_again"
    )
    await db_session.commit()

    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None
    assert refreshed.status == q.STATUS_FAILED
    assert refreshed.last_error == "boom_again"


async def test_requeue_stale_claims_recovers_expired_leases(
    db_session,
):
    job = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None
    # simulate expired lease
    claimed.claim_deadline_at = datetime.now(
        UTC
    ) - timedelta(minutes=5)
    await db_session.commit()

    recovered = await q.requeue_stale_claims(db_session)
    await db_session.commit()
    assert recovered == 1

    refreshed = await db_session.get(ComputeJob, job.id)
    assert refreshed is not None
    assert refreshed.status == q.STATUS_PENDING
    assert refreshed.claimed_by is None
    assert refreshed.claim_deadline_at is None


async def test_requeue_stale_skips_active_claims(db_session):
    await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None
    # lease still in the future — must not be touched
    recovered = await q.requeue_stale_claims(db_session)
    assert recovered == 0


async def test_queue_depth(db_session):
    for tid in (1, 2, 3):
        await q.enqueue(
            db_session,
            job_type="t",
            target_kind="track",
            target_id=tid,
        )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None
    await db_session.commit()

    depth = await q.queue_depth(db_session, job_type="t")
    assert depth.get(q.STATUS_PENDING) == 2
    assert depth.get(q.STATUS_CLAIMED) == 1


async def test_dead_letter_jobs_lists_failed(db_session):
    job = await q.enqueue(
        db_session,
        job_type="t",
        target_kind="track",
        target_id=1,
        max_attempts=1,
    )
    await db_session.commit()
    claimed = await q.claim_next(
        db_session,
        worker_id="w_x",
        job_types=["t"],
    )
    assert claimed is not None
    await q.mark_failed(
        db_session, job=claimed, reason="boom"
    )
    await db_session.commit()

    failed = await q.dead_letter_jobs(db_session)
    assert len(failed) == 1
    assert failed[0].id == job.id
