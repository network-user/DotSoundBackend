from __future__ import annotations

import pytest

from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.services import compute_worker_service as cws

pytestmark = pytest.mark.anyio


async def test_lyrics_claim_respects_pinned_worker(
    db_session,
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
    db_session,
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
