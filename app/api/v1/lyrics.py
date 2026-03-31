"""Lyrics endpoints — CRUD + synced timecodes for tracks."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.lyrics import (
    LyricsCreateRequest,
    LyricsResponse,
    LyricsSyncRequest,
)
from app.services.lyrics_service import LyricsService

router = APIRouter(prefix="/tracks", tags=["lyrics"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.post(
    "/{track_id}/lyrics",
    response_model=LyricsResponse,
    summary="Create or update plain-text lyrics (owner only)",
)
@limiter.limit("30/minute")
async def upsert_lyrics(
    request: Request,
    track_id: int,
    body: LyricsCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    lyrics = await service.create_or_update(
        track_id=track_id, user_id=current_user.id, plain_text=body.plain_text
    )
    return LyricsResponse.model_validate(lyrics)


@router.get(
    "/{track_id}/lyrics",
    response_model=LyricsResponse,
    summary="Get lyrics for a track",
)
@limiter.limit("200/minute")
async def get_lyrics(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    lyrics = await service.get_lyrics(track_id)
    if not lyrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lyrics not found",
        )
    return LyricsResponse.model_validate(lyrics)


@router.put(
    "/{track_id}/lyrics/sync",
    response_model=LyricsResponse,
    summary="Update synced timecodes (owner only). Requires existing plain-text lyrics.",
)
@limiter.limit("30/minute")
async def update_sync(
    request: Request,
    track_id: int,
    body: LyricsSyncRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LyricsResponse:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    synced_dicts = [line.model_dump() for line in body.synced_lines]
    lyrics = await service.update_sync(
        track_id=track_id, user_id=current_user.id, synced_lines=synced_dicts
    )
    return LyricsResponse.model_validate(lyrics)


@router.delete(
    "/{track_id}/lyrics",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete lyrics for a track (owner only)",
)
@limiter.limit("30/minute")
async def delete_lyrics(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    service = LyricsService(session)
    removed = await service.delete_lyrics(
        track_id=track_id, user_id=current_user.id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lyrics not found",
        )
