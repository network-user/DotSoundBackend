from __future__ import annotations

import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.models.artist_features import ArtistFeatures
from app.models.artist_similarity import ArtistSimilarity
from app.models.compute_job import ComputeJob
from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures
from app.models.track_preview_clip import TrackPreviewClip
from app.models.track_similarity import TrackSimilarity
from app.services import compute_queue_service as q
from app.services import compute_results_router as crr

pytestmark = pytest.mark.anyio


def _make_job(
    *,
    job_id: str,
    job_type: str,
    target_kind: str | None,
    target_id: str,
    feature_version: str = "v1",
) -> ComputeJob:
    n = datetime.now(timezone.utc)
    return ComputeJob(
        id=job_id,
        job_type=job_type,
        target_kind=target_kind,
        target_id=target_id,
        feature_version=feature_version,
        next_attempt_at=n,
    )


async def test_persist_track_audio_upsert(
    db_session: AsyncSession,
):
    t = Track(
        title="x",
        file_key="fk",
        source="internal",
    )
    db_session.add(t)
    await db_session.flush()
    job = _make_job(
        job_id="cj_taf_1",
        job_type=q.JOB_TRACK_AUDIO_FEATURES,
        target_kind=q.TARGET_KIND_TRACK,
        target_id=str(t.id),
    )
    await crr.persist_result(
        db_session,
        job=job,
        result={
            "feature_vector": [0.1, 0.2],
            "mood_tags": ["a"],
            "tempo_bpm": 120.0,
            "energy": 0.5,
            "highlight_start_sec": 3.0,
        },
    )
    await db_session.commit()
    row = await db_session.get(
        TrackAudioFeatures,
        t.id,
    )
    assert row is not None
    assert row.mood_tags == ["a"]
    cl = await db_session.get(TrackPreviewClip, t.id)
    assert cl is not None
    assert cl.source == "content_based"


async def test_persist_artist_features(
    db_session: AsyncSession,
):
    a = Artist(
        name="A",
        name_normalized="a",
    )
    db_session.add(a)
    await db_session.flush()
    job = _make_job(
        job_id="cj_af_1",
        job_type=q.JOB_ARTIST_FEATURES_UPDATE,
        target_kind=q.TARGET_KIND_ARTIST,
        target_id=str(a.id),
    )
    await crr.persist_result(
        db_session,
        job=job,
        result={
            "centroid_vector": [1.0, 0.0],
            "dominant_moods": ["m"],
        },
    )
    await db_session.commit()
    row = await db_session.get(ArtistFeatures, a.id)
    assert row is not None
    assert row.dominant_moods == ["m"]


async def test_persist_artist_similarity_replaces(
    db_session: AsyncSession,
):
    a1 = Artist(
        name="A1",
        name_normalized="a1",
    )
    a2 = Artist(
        name="A2",
        name_normalized="a2",
    )
    db_session.add(a1)
    db_session.add(a2)
    await db_session.flush()
    job = _make_job(
        job_id="cj_as_1",
        job_type=q.JOB_ARTIST_SIMILARITY_INDEX,
        target_kind=q.TARGET_KIND_ARTIST,
        target_id=str(a1.id),
    )
    await crr.persist_result(
        db_session,
        job=job,
        result={
            "neighbors": [
                {
                    "similar_artist_id": a2.id,
                    "score": 0.9,
                    "reason_tags": ["x"],
                }
            ],
        },
    )
    await db_session.commit()
    rows = (
        await db_session.execute(
            select(
                ArtistSimilarity.similar_artist_id,
            ).where(
                ArtistSimilarity.artist_id == a1.id,
            )
        )
    ).all()
    assert len(rows) == 1
    assert int(rows[0][0]) == a2.id


async def test_persist_track_similarity(
    db_session: AsyncSession,
):
    t1 = Track(
        title="a",
        source="internal",
    )
    t2 = Track(
        title="b",
        source="internal",
    )
    db_session.add(t1)
    db_session.add(t2)
    await db_session.flush()
    job = _make_job(
        job_id="cj_ts_1",
        job_type=q.JOB_TRACK_SIMILARITY_INDEX,
        target_kind=q.TARGET_KIND_TRACK,
        target_id=str(t1.id),
    )
    await crr.persist_result(
        db_session,
        job=job,
        result={
            "neighbors": [
                {
                    "similar_track_id": t2.id,
                    "score": 0.5,
                }
            ],
        },
    )
    await db_session.commit()
    rows = (
        await db_session.execute(
            select(TrackSimilarity.similar_track_id).where(
                TrackSimilarity.track_id == t1.id
            )
        )
    ).all()
    assert len(rows) == 1


async def test_persist_catalog_normalize(
    db_session: AsyncSession,
):
    t = Track(
        title="old",
        source="internal",
    )
    db_session.add(t)
    await db_session.flush()
    job = _make_job(
        job_id="cj_cat_1",
        job_type=q.JOB_CATALOG_INGEST_NORMALIZE,
        target_kind=q.TARGET_KIND_TRACK,
        target_id=str(t.id),
    )
    await crr.persist_result(
        db_session,
        job=job,
        result={"title": "new", "genre": "g"},
    )
    await db_session.commit()
    await db_session.refresh(t)
    assert t.title == "new"
    assert t.genre == "g"


async def test_unknown_type_raises(
    db_session: AsyncSession,
):
    job = _make_job(
        job_id="cj_bad",
        job_type="nope",
        target_kind="track",
        target_id="1",
    )
    with pytest.raises(
        ValueError,
        match="unknown",
    ):
        await crr.persist_result(
            db_session,
            job=job,
            result={},
        )
