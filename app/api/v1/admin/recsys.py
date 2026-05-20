from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.track import Track
from app.models.user import User
from app.repositories.embedding import EmbeddingRepository
from app.services.audio_embedding_dispatch import (
    enqueue_audio_embedding,
)

router = APIRouter(
    prefix="/recsys/embeddings",
    tags=["admin-recsys-embeddings"],
)


@router.post("/backfill")
async def backfill_embeddings(
    limit: int = Query(50, ge=1, le=1000),
    feature_version: str = Query("v1", min_length=1, max_length=32),
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int | list[int]]:
    repo = EmbeddingRepository(session)
    track_ids = await repo.list_tracks_missing_embedding(
        limit=limit,
    )
    if not track_ids:
        return {"enqueued_count": 0, "track_ids": []}

    rows = await session.execute(
        select(Track)
        .where(Track.id.in_(track_ids))
        .options(selectinload(Track.audio_blob))
    )
    tracks_by_id = {t.id: t for t in rows.scalars().all()}

    enqueued: list[int] = []
    for tid in track_ids:
        track = tracks_by_id.get(tid)
        blob_key = f"track:{tid}"
        if track is not None and track.audio_blob is not None:
            blob_key = track.audio_blob.s3_key
        await enqueue_audio_embedding(
            session,
            track_id=tid,
            audio_blob_key=blob_key,
            feature_version=feature_version,
        )
        enqueued.append(tid)
    return {
        "enqueued_count": len(enqueued),
        "track_ids": enqueued,
    }
