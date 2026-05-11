"""Schedule background processing when a new track enters the catalog."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import compute_queue_service as cqs
from app.services.audio_embedding_dispatch import (
    enqueue_audio_embedding,
)
from app.services.lyrics_service import LyricsService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def schedule_new_track_background_jobs(
    session: AsyncSession,
    track_id: int,
    *,
    skip_lyrics: bool = False,
    catalog_payload: dict[str, Any] | None = None,
) -> None:
    await cqs.enqueue_track_audio_features(
        session,
        track_id=track_id,
        priority=10,
    )
    await cqs.enqueue_catalog_ingest_normalize(
        session,
        track_id=track_id,
        priority=5,
        payload=catalog_payload,
    )
    await enqueue_audio_embedding(
        session,
        track_id=track_id,
        audio_blob_key=f"track:{track_id}",
        priority=8,
    )
    if skip_lyrics:
        logger.info(
            "track_ingest_skipped_lyrics",
            track_id=track_id,
        )
        return
    lyrics = LyricsService(session)
    progress_id = await lyrics.enqueue_background_lyrics(
        track_id,
        requested_by_user_id=None,
        with_sync=True,
        bypass_cache=False,
    )
    if progress_id:
        logger.info(
            "track_ingest_lyrics_enqueued",
            track_id=track_id,
            progress_id=progress_id,
        )
