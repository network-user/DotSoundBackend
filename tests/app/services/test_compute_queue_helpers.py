from __future__ import annotations

import pytest

from app.services import compute_queue_service as q

pytestmark = pytest.mark.anyio


async def test_enqueue_track_audio_idempotent(
    db_session,
):
    j1 = await q.enqueue_track_audio_features(
        db_session,
        track_id=7,
        feature_version="v1",
        priority=10,
    )
    j2 = await q.enqueue_track_audio_features(
        db_session,
        track_id=7,
        feature_version="v1",
        priority=0,
    )
    assert j1.id == j2.id
    assert j1.job_type == q.JOB_TRACK_AUDIO_FEATURES
    assert j1.priority == 10


async def test_queue_health_snapshot_includes_types(
    db_session,
):
    await q.enqueue_track_audio_features(
        db_session,
        track_id=1,
        feature_version="v1",
    )
    await q.enqueue_artist_features(
        db_session,
        artist_id=1,
    )
    await db_session.commit()
    snap = await q.queue_health_snapshot(db_session)
    assert "by_type" in snap
    assert "oldest_pending_sec" in snap
    ta = snap["by_type"][
        q.JOB_TRACK_AUDIO_FEATURES
    ]
    assert int(ta.get(q.STATUS_PENDING) or 0) >= 1
    ap = q.JOB_ARTIST_FEATURES_UPDATE
    ad = snap["by_type"].get(
        ap,
    )
    assert int(ad.get(q.STATUS_PENDING) or 0) >= 1
    o = snap["oldest_pending_sec"]
    assert ap in o or q.JOB_TRACK_AUDIO_FEATURES in o
