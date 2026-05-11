"""Track post-upload processing progress (SSE + status snapshot).

Public-facing workflow stages exposed to the client:
- ``uploaded`` → ``cover`` → ``audio_analysis`` → ``lyrics`` → ``ready``
- terminal ``error`` if any stage fails irrecoverably

These are opaque labels; internal pipeline names, providers and
ML-tier identifiers are NOT included in any payload.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.compute_job import ComputeJob
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.user import User

router = APIRouter(prefix="", tags=["tracks-processing"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_POLL_INTERVAL_SECONDS = 2.0
_MAX_TICKS = 150  # 150 * 2s = 5 minutes
_AUDIO_FEATURES_JOB = "track_audio_features"
_CATALOG_NORMALIZE_JOB = "catalog_ingest_normalize"


class ProcessingSnapshot(BaseModel):
    track_id: int
    uploaded: str
    cover: str
    audio_analysis: str
    lyrics: str
    overall: str


@router.get(
    "/{track_id}/processing/status",
    response_model=ProcessingSnapshot,
    summary="Snapshot of post-upload processing stages",
)
@limiter.limit("60/minute")
async def get_processing_status(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessingSnapshot:
    track = await _load_owned_track(session, track_id, current_user.id)
    return await _compute_snapshot(session, track)


@router.get(
    "/{track_id}/processing/events",
    summary="SSE stream of post-upload processing stage updates",
)
async def stream_processing_events(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    track = await _load_owned_track(session, track_id, current_user.id)

    async def event_generator() -> AsyncIterator[str]:
        last_payload: dict[str, Any] | None = None
        try:
            for _ in range(_MAX_TICKS):
                if await request.is_disconnected():
                    break
                snapshot = await _compute_snapshot(session, track)
                payload = snapshot.model_dump()
                if payload != last_payload:
                    yield _sse_event("snapshot", payload)
                    last_payload = payload
                if snapshot.overall in {"ready", "error"}:
                    break
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            else:
                yield _sse_event("timeout", {"track_id": track_id})
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _load_owned_track(
    session: AsyncSession, track_id: int, user_id: int
) -> Track:
    track = await session.get(Track, track_id)
    if track is None or track.uploaded_by_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    return track


async def _compute_snapshot(
    session: AsyncSession, track: Track
) -> ProcessingSnapshot:
    await session.refresh(track, attribute_names=["cover_key"])
    cover_stage = "done" if track.cover_key else "pending"

    audio_status = await _get_compute_job_status(
        session, track.id, _AUDIO_FEATURES_JOB
    )
    catalog_status = await _get_compute_job_status(
        session, track.id, _CATALOG_NORMALIZE_JOB
    )
    audio_stage = _combine_compute_stages(audio_status, catalog_status)

    lyrics_result = await session.execute(
        select(TrackLyrics).where(TrackLyrics.track_id == track.id)
    )
    lyrics_row = lyrics_result.scalar_one_or_none()
    lyrics_stage = _derive_lyrics_stage(lyrics_row, audio_stage)

    overall = _derive_overall(cover_stage, audio_stage, lyrics_stage)
    return ProcessingSnapshot(
        track_id=track.id,
        uploaded="done",
        cover=cover_stage,
        audio_analysis=audio_stage,
        lyrics=lyrics_stage,
        overall=overall,
    )


async def _get_compute_job_status(
    session: AsyncSession, track_id: int, job_type: str
) -> str | None:
    result = await session.execute(
        select(ComputeJob.status)
        .where(
            ComputeJob.target_kind == "track",
            ComputeJob.target_id == str(track_id),
            ComputeJob.job_type == job_type,
        )
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if isinstance(row, str) else None


def _map_compute_status(raw: str | None) -> str:
    if raw is None:
        return "pending"
    if raw in {"done", "succeeded"}:
        return "done"
    if raw in {"failed", "error", "cancelled"}:
        return "error"
    if raw in {"claimed", "running", "in_progress"}:
        return "running"
    return "pending"


def _combine_compute_stages(*statuses: str | None) -> str:
    mapped = [_map_compute_status(s) for s in statuses]
    if any(m == "error" for m in mapped):
        return "error"
    if all(m == "done" for m in mapped):
        return "done"
    if any(m == "running" for m in mapped):
        return "running"
    return "pending"


def _derive_lyrics_stage(
    lyrics_row: TrackLyrics | None, audio_stage: str
) -> str:
    if lyrics_row is not None:
        return "done"
    if audio_stage in {"pending", "running"}:
        return "running"
    return "pending"


def _derive_overall(cover: str, audio: str, lyrics: str) -> str:
    parts = (cover, audio, lyrics)
    if any(p == "error" for p in parts):
        return "error"
    if all(p == "done" or p == "skipped" for p in parts):
        return "ready"
    return "processing"


def _sse_event(name: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"
