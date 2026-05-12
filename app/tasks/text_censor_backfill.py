"""One-shot backfill: apply text censorship to all existing content.

Processes tracks.description, track_lyrics.plain_text +
synced_lines, and track_lyrics_translations.translated_text in
batches of 500.  Only rows whose text actually changes are written.

Run once after deploying the censorship feature:
  POST /api/v1/admin/tasks/text-censor-backfill
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select, update

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.lyrics import TrackLyrics
from app.models.lyrics_translation import (
    TrackLyricsTranslation,
)
from app.models.track import Track
from dotsound_private_core import (
    censor_synced_lines,
    censor_text,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_BATCH = 500


async def _backfill_descriptions(
    counts: dict[str, int],
) -> None:
    offset = 0
    while True:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(Track.id, Track.description)
                    .where(Track.description.isnot(None))
                    .order_by(Track.id)
                    .limit(_BATCH)
                    .offset(offset)
                )
            ).all()
            if not rows:
                break
            changed: list[dict[str, Any]] = []
            for row_id, desc in rows:
                censored = censor_text(desc)
                if censored != desc:
                    changed.append(
                        {"id": row_id, "description": censored}
                    )
            if changed:
                for item in changed:
                    await session.execute(
                        update(Track)
                        .where(Track.id == item["id"])
                        .values(description=item["description"])
                    )
                await session.commit()
                counts["tracks"] += len(changed)
        offset += _BATCH


async def _backfill_lyrics(
    counts: dict[str, int],
) -> None:
    offset = 0
    while True:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(
                        TrackLyrics.id,
                        TrackLyrics.plain_text,
                        TrackLyrics.synced_lines,
                    )
                    .where(TrackLyrics.plain_text.isnot(None))
                    .order_by(TrackLyrics.id)
                    .limit(_BATCH)
                    .offset(offset)
                )
            ).all()
            if not rows:
                break
            changed: list[dict[str, Any]] = []
            for row_id, plain, synced in rows:
                new_plain = censor_text(plain)
                new_synced = (
                    censor_synced_lines(synced)
                    if isinstance(synced, list)
                    else synced
                )
                if new_plain != plain or new_synced != synced:
                    changed.append(
                        {
                            "id": row_id,
                            "plain_text": new_plain,
                            "synced_lines": new_synced,
                        }
                    )
            if changed:
                for item in changed:
                    await session.execute(
                        update(TrackLyrics)
                        .where(TrackLyrics.id == item["id"])
                        .values(
                            plain_text=item["plain_text"],
                            synced_lines=item["synced_lines"],
                        )
                    )
                await session.commit()
                counts["lyrics"] += len(changed)
        offset += _BATCH


async def _backfill_translations(
    counts: dict[str, int],
) -> None:
    offset = 0
    while True:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(
                        TrackLyricsTranslation.id,
                        TrackLyricsTranslation.translated_text,
                    )
                    .where(
                        TrackLyricsTranslation.translated_text.isnot(
                            None
                        )
                    )
                    .order_by(TrackLyricsTranslation.id)
                    .limit(_BATCH)
                    .offset(offset)
                )
            ).all()
            if not rows:
                break
            changed: list[dict[str, Any]] = []
            for row_id, text in rows:
                censored = censor_text(text)
                if censored != text:
                    changed.append(
                        {"id": row_id, "translated_text": censored}
                    )
            if changed:
                for item in changed:
                    await session.execute(
                        update(TrackLyricsTranslation)
                        .where(
                            TrackLyricsTranslation.id == item["id"]
                        )
                        .values(
                            translated_text=item["translated_text"]
                        )
                    )
                await session.commit()
                counts["translations"] += len(changed)
        offset += _BATCH


@broker.task
async def text_censor_backfill_task() -> dict[str, int]:
    counts: dict[str, int] = {
        "tracks": 0,
        "lyrics": 0,
        "translations": 0,
    }
    await _backfill_descriptions(counts)
    await _backfill_lyrics(counts)
    await _backfill_translations(counts)
    logger.info("text_censor_backfill_done", **counts)
    return counts


__all__ = ["text_censor_backfill_task"]
