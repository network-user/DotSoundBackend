"""Aggregator endpoint for the post-upload track edit screen.

Returns the editable fields of a track plus a few capability flags
in a single request, so the client avoids a waterfall when opening
``/track/:id/edit``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.user import User
from app.schemas.upload_chunked import TrackEditContextResponse

router = APIRouter()


@router.get(
    "/{track_id}/edit-context",
    response_model=TrackEditContextResponse,
)
@limiter.limit("60/minute")
async def get_edit_context(
    request: Request,
    track_id: int = Path(..., ge=1),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackEditContextResponse:
    result = await session.execute(
        select(Track).where(
            Track.id == track_id,
            Track.is_active.is_(True),
        )
    )
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    owns = track.uploaded_by_id == current_user.id
    if not owns and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to edit this track",
        )

    lyrics_row = await session.execute(
        select(TrackLyrics.track_id).where(
            TrackLyrics.track_id == track_id
        )
    )
    has_lyrics = lyrics_row.scalar_one_or_none() is not None

    is_processing = track.processing_status == "processing"

    return TrackEditContextResponse(
        track_id=track.id,
        title=track.title,
        artist=track.artist,
        genre=track.genre,
        description=track.description,
        is_public=track.is_public,
        cover_key=track.cover_key,
        has_lyrics=has_lyrics,
        is_processing=is_processing,
        can_edit_artist=owns or current_user.is_admin,
        can_delete=owns or current_user.is_admin,
    )
