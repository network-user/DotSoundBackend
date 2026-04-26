from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_features import ArtistFeatures
from app.models.artist_similarity import ArtistSimilarity
from app.models.compute_job import ComputeJob
from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures
from app.models.track_preview_clip import TrackPreviewClip
from app.models.track_similarity import TrackSimilarity
from app.services import compute_queue_service as q

SIMILARITY_INDEX_MAX_EDGES = 500


def _i(x: str | int | None) -> int:
    if x is None:
        return 0
    return int(x)


def _f(x: object) -> float | None:
    if x is None:
        return None
    try:
        return float(cast(Any, x))
    except (TypeError, ValueError):
        return None


async def persist_result(
    session: AsyncSession,
    job: ComputeJob,
    result: dict[str, Any] | None,
) -> None:
    r: dict[str, Any] = result or {}
    if job.job_type == q.JOB_TRACK_AUDIO_FEATURES:
        await _persist_track_audio(
            session,
            job=job,
            r=r,
        )
        return
    if job.job_type == q.JOB_ARTIST_FEATURES_UPDATE:
        await _persist_artist_features(
            session,
            job=job,
            r=r,
        )
        return
    if job.job_type == q.JOB_ARTIST_SIMILARITY_INDEX:
        await _persist_artist_similarity_index(
            session,
            job=job,
            r=r,
        )
        return
    if job.job_type == q.JOB_TRACK_SIMILARITY_INDEX:
        await _persist_track_similarity_index(
            session,
            job=job,
            r=r,
        )
        return
    if job.job_type == q.JOB_CATALOG_INGEST_NORMALIZE:
        await _persist_catalog_normalize(
            session,
            job=job,
            r=r,
        )
        return
    raise ValueError(f"unknown_job_type:{job.job_type}")


async def _persist_track_audio(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    tid = _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    if tid <= 0:
        raise ValueError("track_audio_features_invalid_target")
    row = await session.get(TrackAudioFeatures, tid)
    fv = r.get("feature_vector")
    mtags = r.get("mood_tags")
    t_bpm = _f(r.get("tempo_bpm"))
    en = _f(r.get("energy"))
    hlight = _f(r.get("highlight_start_sec"))
    fv_o = r.get("feature_version")
    fver: str = str(fv_o) if isinstance(
        fv_o, str
    ) else str(job.feature_version)
    if row is None:
        row = TrackAudioFeatures(
            track_id=tid,
            feature_version=fver,
        )
        session.add(row)
    if fv is not None:
        row.feature_vector = fv
    if mtags is not None:
        row.mood_tags = mtags
    if t_bpm is not None:
        row.tempo_bpm = t_bpm
    if en is not None:
        row.energy = en
    if hlight is not None:
        row.highlight_start_sec = hlight
    row.feature_version = fver

    clip_start = hlight
    if clip_start is not None and clip_start >= 0.0:
        tr_row = await session.get(Track, tid)
        clip = await session.get(TrackPreviewClip, tid)
        dur = 15.0
        if tr_row and tr_row.duration_seconds is not None:
            dur = min(
                15.0,
                max(
                    0.1,
                    float(tr_row.duration_seconds) - float(clip_start),
                ),
            )
        if clip is None:
            session.add(
                TrackPreviewClip(
                    track_id=tid,
                    start_sec=float(clip_start),
                    duration_sec=dur,
                    source="content_based",
                )
            )
        else:
            clip.start_sec = float(clip_start)
            clip.duration_sec = dur
            clip.source = "content_based"


async def _persist_artist_features(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    aid = _i(job.target_id) if job.target_kind == q.TARGET_KIND_ARTIST else 0
    if aid <= 0:
        raise ValueError("artist_features_invalid_target")
    row = await session.get(ArtistFeatures, aid)
    fvo = r.get("feature_version")
    fver2: str = str(fvo) if isinstance(
        fvo, str
    ) else str(job.feature_version)
    if row is None:
        row = ArtistFeatures(
            artist_id=aid,
            feature_version=fver2,
        )
        session.add(row)
    if r.get("centroid_vector") is not None:
        row.centroid_vector = r.get("centroid_vector")
    if r.get("dominant_moods") is not None:
        row.dominant_moods = r.get("dominant_moods")
    if r.get("style_tags") is not None:
        row.style_tags = r.get("style_tags")
    row.feature_version = fver2


async def _persist_artist_similarity_index(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    aid = _i(job.target_id) if job.target_kind == q.TARGET_KIND_ARTIST else 0
    if aid <= 0:
        raise ValueError("artist_similarity_invalid_target")
    edges = r.get("neighbors")
    if not isinstance(edges, list):
        raise ValueError("artist_similarity_neighbors_required")
    edges = edges[:SIMILARITY_INDEX_MAX_EDGES]
    fvo3 = r.get("feature_version")
    fver3: str = str(fvo3) if isinstance(
        fvo3, str
    ) else str(job.feature_version)
    await session.execute(
        delete(ArtistSimilarity).where(
            ArtistSimilarity.artist_id == aid,
            ArtistSimilarity.feature_version == fver3,
        )
    )
    for e in edges:
        if not isinstance(e, dict):
            continue
        o = _i(e.get("similar_artist_id") or e.get("artist_id"))
        if o <= 0 or o == aid:
            continue
        sc = _f(e.get("score"))
        if sc is None:
            continue
        session.add(
            ArtistSimilarity(
                artist_id=aid,
                similar_artist_id=o,
                score=sc,
                reason_tags=e.get("reason_tags")
                if isinstance(
                    e.get("reason_tags"),
                    list,
                )
                else None,
                feature_version=fver3,
            )
        )


async def _persist_track_similarity_index(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    tid = _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    if tid <= 0:
        raise ValueError("track_similarity_invalid_target")
    edges = r.get("neighbors")
    if not isinstance(edges, list):
        raise ValueError("track_similarity_neighbors_required")
    edges = edges[:SIMILARITY_INDEX_MAX_EDGES]
    fvo4 = r.get("feature_version")
    fver4: str = str(fvo4) if isinstance(
        fvo4, str
    ) else str(job.feature_version)
    await session.execute(
        delete(TrackSimilarity).where(
            TrackSimilarity.track_id == tid,
            TrackSimilarity.feature_version == fver4,
        )
    )
    for e in edges:
        if not isinstance(e, dict):
            continue
        o = _i(
            e.get("similar_track_id")
            or e.get("track_id")
        )
        if o <= 0 or o == tid:
            continue
        sc = _f(e.get("score"))
        if sc is None:
            continue
        session.add(
            TrackSimilarity(
                track_id=tid,
                similar_track_id=o,
                score=sc,
                reason_tags=e.get("reason_tags")
                if isinstance(
                    e.get("reason_tags"),
                    list,
                )
                else None,
                feature_version=fver4,
            )
        )


async def _persist_catalog_normalize(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    tid = _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    if tid <= 0:
        raise ValueError("catalog_normalize_invalid_target")
    tr = await session.get(Track, tid)
    if tr is None:
        raise ValueError("catalog_track_missing")
    t = r.get("title")
    if isinstance(t, str) and t.strip():
        tr.title = t[:256]
    a = r.get("artist")
    if isinstance(a, str):
        tr.artist = a[:256] if a else None
    g = r.get("genre")
    if isinstance(g, str):
        tr.genre = g[:100] if g else None


async def get_compute_job_for_worker(
    session: AsyncSession,
    job_id: str,
    worker_id: str,
) -> ComputeJob | None:
    stmt = select(ComputeJob).where(
        ComputeJob.id == job_id,
        ComputeJob.claimed_by == worker_id,
    )
    return (
        await session.execute(stmt)
    ).scalar_one_or_none()


__all__ = [
    "get_compute_job_for_worker",
    "persist_result",
    "SIMILARITY_INDEX_MAX_EDGES",
]
