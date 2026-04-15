from __future__ import annotations

import asyncio
import os
import tempfile

import structlog
from sqlalchemy import select

from app.config import settings
from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.repositories.lyrics import LyricsRepository

logger = structlog.stdlib.get_logger(__name__)


@broker.task
async def generate_lyrics_task(
    track_id: int,
    with_sync: bool = False,
) -> dict:
    structlog.contextvars.bind_contextvars(
        track_id=track_id
    )
    logger.info(
        "lyrics_generation_started", with_sync=with_sync
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track).where(Track.id == track_id)
        )
        track = result.scalar_one_or_none()
        if not track or not track.is_active:
            logger.warning("lyrics_track_not_found")
            return {"status": "error", "detail": "track_not_found"}

        artist = track.artist or ""
        title = track.title or ""

        audio_path: str | None = None
        tmp_dir: str | None = None

        try:
            if with_sync and track.file_key:
                tmp_dir = tempfile.mkdtemp()
                audio_path = os.path.join(
                    tmp_dir, "audio.mp3"
                )
                data = await s3.download_object(
                    track.file_key
                )
                with open(audio_path, "wb") as f:
                    f.write(data)

            from dotsound_private_core.services.lyrics_provider import (  # noqa: E501
                generate_lyrics,
            )

            gen_result = await asyncio.to_thread(
                generate_lyrics,
                artist=artist,
                title=title,
                api_token=settings.lyrics_provider_token,
                audio_path=audio_path,
                model_size=settings.provider_model_size,
            )

            if gen_result is None:
                logger.info("lyrics_not_found")
                return {"status": "not_found"}

            synced_dicts: list[dict] | None = None
            if gen_result.synced_lines:
                synced_dicts = [
                    {
                        "time_ms": sl.time_ms,
                        "text": sl.text,
                    }
                    for sl in gen_result.synced_lines
                ]

            repo = LyricsRepository(session)
            await repo.create_or_update(
                track_id=track_id,
                plain_text=gen_result.text,
                source="auto",
                synced_lines=synced_dicts,
            )
            await session.commit()

            has_sync = synced_dicts is not None
            logger.info(
                "lyrics_generation_done",
                has_sync=has_sync,
            )
            return {
                "status": "found",
                "has_sync": has_sync,
            }

        except Exception:
            logger.exception("lyrics_generation_error")
            return {"status": "error"}
        finally:
            if tmp_dir and os.path.isdir(tmp_dir):
                import shutil

                shutil.rmtree(tmp_dir, ignore_errors=True)
