"""Apply heuristic genre/mood hints after lyrics text is saved."""

from __future__ import annotations

import structlog
from dotsound_private_core.services.text_genre_mood_infer import (
    infer_genre_and_moods_from_lyrics,
    normalize_genre_label,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.track import Track
from app.models.track_audio_features import TrackAudioFeatures

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_MOOD_TAGS = 16


async def apply_after_lyrics_saved(
    session: AsyncSession,
    track_id: int,
    plain_text: str,
) -> None:
    if not settings.lyrics_derived_genre_mood_enabled:
        return
    if not plain_text.strip():
        return
    track = await session.get(Track, track_id)
    if track is None or not track.is_active:
        return
    sig = infer_genre_and_moods_from_lyrics(
        lyrics=plain_text,
        title=track.title,
        artist=track.artist,
    )
    changed = False
    if sig.genre_guess and not (track.genre and track.genre.strip()):
        label = normalize_genre_label(sig.genre_guess)
        if label:
            track.genre = label
            changed = True
    if sig.mood_tags:
        row = await session.get(TrackAudioFeatures, track_id)
        if row is None:
            row = TrackAudioFeatures(track_id=track_id)
            session.add(row)
        existing_cf: list[str] = []
        if row.mood_tags:
            for x in row.mood_tags:
                if isinstance(x, str) and x.strip():
                    existing_cf.append(x.casefold())
        new_tags = [
            m for m in sig.mood_tags if m.casefold() not in existing_cf
        ]
        if new_tags:
            merged_cf = existing_cf + [m.casefold() for m in new_tags]
            merged_cf = merged_cf[:_MAX_MOOD_TAGS]
            row.mood_tags = merged_cf
            changed = True
    if changed:
        await session.flush()
        logger.info("lyrics_derived_genre_mood_applied", track_id=track_id)
