"""Audio-embedding job dispatch.

Thin wrapper that turns a "this track now has playable audio"
event into an idempotent compute job for ``DotSoundComputeWorker``.
The worker pulls jobs of type :data:`AUDIO_EMBEDDING_JOB_TYPE`,
runs the opaque extractor, and posts the resulting vector back via
the existing internal-bridge endpoints.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob
from app.services.compute_queue_service import enqueue

AUDIO_EMBEDDING_JOB_TYPE = "audio_embedding"
DEFAULT_FEATURE_VERSION = "v1"

logger = structlog.get_logger(__name__)


async def enqueue_audio_embedding(
    session: AsyncSession,
    *,
    track_id: int,
    audio_blob_key: str,
    feature_version: str = DEFAULT_FEATURE_VERSION,
    priority: int = 0,
) -> ComputeJob:
    job = await enqueue(
        session,
        job_type=AUDIO_EMBEDDING_JOB_TYPE,
        target_kind="track",
        target_id=int(track_id),
        payload={
            "audio_blob_key": audio_blob_key,
        },
        feature_version=feature_version,
        priority=priority,
    )
    logger.info(
        "audio_embedding_job_enqueued",
        track_id=track_id,
        job_id=job.id,
        feature_version=feature_version,
    )
    return job
