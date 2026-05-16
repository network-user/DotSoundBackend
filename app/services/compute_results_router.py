from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist_features import ArtistFeatures
from app.models.artist_similarity import ArtistSimilarity
from app.models.compute_job import ComputeJob
from app.models.import_job import ImportJob
from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures
from app.models.track_preview_clip import TrackPreviewClip
from app.models.track_similarity import TrackSimilarity
from app.models.track_snippet import TrackSnippet
from app.repositories.embedding import EmbeddingRepository
from app.repositories.track_info import TrackInfoRepository
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
    job_type = q.canonical_job_type(job.job_type)
    if job_type == q.JOB_TRACK_AUDIO_FEATURES:
        await _persist_track_audio(
            session,
            job=job,
            r=r,
        )
        return
    if job_type == q.JOB_ARTIST_FEATURES_UPDATE:
        await _persist_artist_features(
            session,
            job=job,
            r=r,
        )
        return
    if job_type == q.JOB_ARTIST_SIMILARITY:
        await _persist_artist_similarity_index(
            session,
            job=job,
            r=r,
        )
        return
    if job_type == q.JOB_TRACK_SIMILARITY:
        await _persist_track_similarity_index(
            session,
            job=job,
            r=r,
        )
        return
    if job_type == q.JOB_CATALOG_NORMALIZE:
        await _persist_catalog_normalize(
            session,
            job=job,
            r=r,
        )
        return
    if job_type == q.JOB_AUDIO_EMBEDDING:
        await _persist_audio_embedding(
            session,
            job=job,
            r=r,
        )
        return
    if job_type == q.JOB_SOUNDCLOUD_RPC:
        await _persist_soundcloud_rpc(
            session,
            job=job,
            r=r,
        )
        return
    if job_type in (
        q.JOB_SC_ARTIST_CATALOG_SYNC,
        q.JOB_SC_ARTIST_SIMILAR_STATION_SYNC,
        q.JOB_SC_ARTIST_RELEASE_SYNC,
    ):
        await _persist_catalog_sync_result(session, job=job, r=r)
        return
    if job_type == q.JOB_ARTIST_ENRICHMENT:
        await _persist_artist_enrichment(session, job=job, r=r)
        return
    if job_type == q.JOB_TRACK_INFO_FETCH:
        await _persist_track_info(session, job=job, r=r)
        return
    if job_type == q.JOB_EXTERNAL_IMPORT_SCAN:
        await _persist_external_import_scan(session, job=job, r=r)
        return
    if job_type == q.JOB_TRACK_TRANSCODING:
        await _persist_track_transcoding(session, job=job, r=r)
        return
    if job_type == q.JOB_TRACK_WAVEFORM:
        await _persist_track_waveform(session, job=job, r=r)
        return
    if job_type == q.JOB_TRACK_SNIPPET:
        await _persist_track_snippet(session, job=job, r=r)
        return
    if job_type == q.JOB_TRACK_COVER_PROCESSING:
        await _persist_track_cover(session, job=job, r=r)
        return
    raise ValueError(f"unknown_job_type:{job.job_type}")


async def _persist_catalog_sync_result(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    from app.services import artist_catalog_sync_progress as acsp

    artist_id = _i(job.target_id)
    if artist_id <= 0:
        raise ValueError("catalog_sync_invalid_target")
    mode = "full"
    soundcloud_album_id: int | None = None
    job_type = q.canonical_job_type(job.job_type)
    if job_type == q.JOB_SC_ARTIST_SIMILAR_STATION_SYNC:
        mode = "station"
    elif job_type == q.JOB_SC_ARTIST_RELEASE_SYNC:
        mode = "release"
        raw_album_id = r.get("soundcloud_album_id") or (job.payload or {}).get(
            "soundcloud_album_id"
        )
        soundcloud_album_id = _i(raw_album_id)
    status = str(r.get("status") or "ok")
    if status in {"ok", "done", "partial_skipped_dead_track"}:
        await acsp.set_success(
            artist_id,
            mode=mode,
            soundcloud_album_id=soundcloud_album_id,
            detail=r,
        )
    elif status == "queued_compute":
        await acsp.set_running(
            artist_id,
            mode=mode,
            soundcloud_album_id=soundcloud_album_id,
            detail=r,
        )
    else:
        await acsp.set_error(
            artist_id,
            mode=mode,
            soundcloud_album_id=soundcloud_album_id,
            message=str(r.get("error") or r.get("reason") or status),
        )


async def _persist_artist_enrichment(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    artist_id = (
        _i(job.target_id) if job.target_kind == q.TARGET_KIND_ARTIST else 0
    )
    if artist_id <= 0:
        raise ValueError("artist_enrichment_invalid_target")
    status = str(r.get("status") or "")
    if status not in {"", "ok", "done", "not_found", "error"}:
        raise ValueError("artist_enrichment_invalid_status")


async def _persist_track_info(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    track_id = (
        _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    )
    if track_id <= 0:
        raise ValueError("track_info_invalid_target")
    status = str(r.get("status") or "done")
    content_obj = r.get("content")
    content = content_obj[:12_000] if isinstance(content_obj, str) else None
    fetched_at = (
        datetime.now(UTC)
        if status in {"done", "not_found", "failed"}
        else None
    )
    await TrackInfoRepository(session).upsert(
        track_id,
        status=status,
        content=content,
        fetched_at=fetched_at,
    )


async def _persist_external_import_scan(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    import_job_id = _i(job.target_id)
    if import_job_id <= 0:
        raise ValueError("external_import_scan_invalid_target")
    row = await session.get(ImportJob, import_job_id)
    if row is None:
        raise ValueError("external_import_scan_missing_job")
    status = str(r.get("status") or row.status)
    if status:
        row.status = status
    total = r.get("total_tracks")
    if isinstance(total, int):
        row.total_tracks = total
    completed = r.get("completed_tracks")
    if isinstance(completed, int):
        row.completed_tracks = completed
    failed = r.get("failed_tracks")
    if isinstance(failed, int):
        row.failed_tracks = failed
    data = r.get("tracks_data")
    if isinstance(data, dict):
        row.tracks_data = data


async def _persist_track_transcoding(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    track_id = (
        _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    )
    if track_id <= 0:
        raise ValueError("track_transcoding_invalid_target")
    track = await session.get(Track, track_id)
    if track is None:
        raise ValueError("track_transcoding_missing_track")
    _set_track_audio_fields(track, r)


async def _persist_track_waveform(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    track_id = (
        _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    )
    if track_id <= 0:
        raise ValueError("track_waveform_invalid_target")
    track = await session.get(Track, track_id)
    if track is None:
        raise ValueError("track_waveform_missing_track")
    waveform = r.get("waveform_data") or r.get("waveform")
    if isinstance(waveform, list):
        track.waveform_data = [
            float(v) for v in waveform if isinstance(v, int | float)
        ]


async def _persist_track_snippet(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    snippet_id = _i(job.target_id)
    if snippet_id <= 0:
        raise ValueError("track_snippet_invalid_target")
    row = await session.get(TrackSnippet, snippet_id)
    if row is None:
        raise ValueError("track_snippet_missing")
    file_key = r.get("file_key")
    if isinstance(file_key, str) and file_key:
        row.file_key = file_key
    status = r.get("status")
    if isinstance(status, str) and status:
        row.status = status[:20]
    error = r.get("error") or r.get("error_message")
    if isinstance(error, str):
        row.error_message = error[:2000]


async def _persist_track_cover(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    track_id = (
        _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    )
    if track_id <= 0:
        raise ValueError("track_cover_invalid_target")
    track = await session.get(Track, track_id)
    if track is None:
        raise ValueError("track_cover_missing_track")
    cover_key = r.get("cover_key")
    if isinstance(cover_key, str) and cover_key:
        track.cover_key = cover_key


def _set_track_audio_fields(track: Track, r: dict[str, Any]) -> None:
    file_key = r.get("file_key")
    if isinstance(file_key, str) and file_key:
        track.file_key = file_key
    status = r.get("processing_status") or r.get("status")
    if isinstance(status, str) and status:
        track.processing_status = status[:20]
    file_size = r.get("file_size_bytes")
    if isinstance(file_size, int):
        track.file_size_bytes = file_size
    hls_manifest_key = r.get("hls_manifest_key")
    if isinstance(hls_manifest_key, str) and hls_manifest_key:
        track.hls_manifest_key = hls_manifest_key
    hls_segment_seconds = r.get("hls_segment_seconds")
    if isinstance(hls_segment_seconds, int):
        track.hls_segment_seconds = hls_segment_seconds
    hls_bundle_version = r.get("hls_bundle_version")
    if isinstance(hls_bundle_version, int):
        track.hls_bundle_version = hls_bundle_version


async def _persist_soundcloud_rpc(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    """Mirror the RPC envelope into Redis under the request id.

    SoundCloud RPC is a synchronous-style call: a backend caller
    enqueues the job, then waits (via :mod:`app.services.sc_rpc_client`)
    for the result envelope to appear in Redis. The ``ComputeJob`` row
    itself is the durable record; this side-channel just spares
    callers a DB poll loop on every fetch.

    The persisted blob is the **whole** envelope so consumers see
    ``success / error_kind / upstream_status`` without re-loading
    the row.
    """
    import json

    from app.core.redis import get_redis_client

    request_id = job.target_id or job.id
    key = f"sc_rpc_result:{request_id}"
    payload = {
        "envelope": r,
        "job_id": job.id,
    }
    try:
        redis = get_redis_client()
        await redis.set(key, json.dumps(payload), ex=60 * 60)
        await redis.publish(
            f"sc_rpc_result_chan:{request_id}",
            json.dumps({"job_id": job.id}),
        )
    except Exception:
        # The ComputeJob row still has the result; sc_rpc_client
        # falls back to polling job.result in that case.
        pass


async def _persist_audio_embedding(
    session: AsyncSession,
    *,
    job: ComputeJob,
    r: dict[str, Any],
) -> None:
    tid = _i(job.target_id) if job.target_kind == q.TARGET_KIND_TRACK else 0
    if tid <= 0:
        raise ValueError("audio_embedding_invalid_target")
    raw_embedding = r.get("embedding") or []
    if not isinstance(raw_embedding, list) or not raw_embedding:
        return
    vector: list[float] = []
    for value in raw_embedding:
        try:
            vector.append(float(value))
        except (TypeError, ValueError):
            return
    model_version = (
        str(r.get("model_version"))
        if r.get("model_version")
        else str(job.feature_version)
    )
    repo = EmbeddingRepository(session)
    await repo.upsert(
        track_id=tid,
        embedding=vector,
        model_version=model_version,
    )


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
    fver: str = (
        str(fv_o) if isinstance(fv_o, str) else str(job.feature_version)
    )
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
    fver2: str = str(fvo) if isinstance(fvo, str) else str(job.feature_version)
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
    fver3: str = (
        str(fvo3) if isinstance(fvo3, str) else str(job.feature_version)
    )
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
                reason_tags=(
                    e.get("reason_tags")
                    if isinstance(
                        e.get("reason_tags"),
                        list,
                    )
                    else None
                ),
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
    fver4: str = (
        str(fvo4) if isinstance(fvo4, str) else str(job.feature_version)
    )
    await session.execute(
        delete(TrackSimilarity).where(
            TrackSimilarity.track_id == tid,
            TrackSimilarity.feature_version == fver4,
        )
    )
    for e in edges:
        if not isinstance(e, dict):
            continue
        o = _i(e.get("similar_track_id") or e.get("track_id"))
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
                reason_tags=(
                    e.get("reason_tags")
                    if isinstance(
                        e.get("reason_tags"),
                        list,
                    )
                    else None
                ),
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
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "get_compute_job_for_worker",
    "persist_result",
    "SIMILARITY_INDEX_MAX_EDGES",
]
