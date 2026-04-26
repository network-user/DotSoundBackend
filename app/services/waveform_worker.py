from __future__ import annotations

import asyncio
import os
import struct
import tempfile

import structlog
from sqlalchemy import select, update

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.repositories.app_settings import AppSettingsRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_NUM_BARS = 200
_SETTING_KEY = "migration.waveform_backfill_v1"


def _pcm_to_waveform(pcm_bytes: bytes) -> list[float]:
    """Convert raw 16-bit mono PCM bytes to a normalized 200-bar waveform."""
    if not pcm_bytes:
        return [0.0] * _NUM_BARS
    samples = struct.unpack(f"<{len(pcm_bytes) // 2}h", pcm_bytes)
    if not samples:
        return [0.0] * _NUM_BARS
    chunk = max(1, len(samples) // _NUM_BARS)
    bars: list[float] = []
    for i in range(_NUM_BARS):
        window = samples[i * chunk : (i + 1) * chunk]
        if window:
            rms = (sum(s * s for s in window) / len(window)) ** 0.5
            bars.append(rms)
        else:
            bars.append(0.0)
    peak = max(bars) or 1.0
    return [round(v / peak, 4) for v in bars]


async def _generate_for_track_id(track_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track.file_key).where(Track.id == track_id)
        )
        row = result.first()
        if row is None or not row[0]:
            logger.warning("waveform_no_file_key", track_id=track_id)
            return False
        file_key = row[0]

    from app.core import s3

    try:
        mp3_data = await s3.download_object(file_key)
    except Exception:
        logger.warning("waveform_s3_download_failed", track_id=track_id)
        return False

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    try:
        tmp.write(mp3_data)
        tmp.flush()
        tmp_path = tmp.name
    finally:
        tmp.close()

    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", tmp_path,
            "-ac", "1",
            "-ar", "8000",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        pcm_data, _ = await process.communicate()
    except Exception:
        logger.warning("waveform_ffmpeg_failed", track_id=track_id)
        return False
    finally:
        os.unlink(tmp_path)

    if not pcm_data:
        logger.warning("waveform_empty_pcm", track_id=track_id)
        return False

    waveform = _pcm_to_waveform(pcm_data)

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(waveform_data=waveform)
        )
        await session.commit()

    logger.info("waveform_generated", track_id=track_id, bars=len(waveform))
    return True


@broker.task
async def generate_waveform_task(track_id: int) -> None:
    structlog.contextvars.bind_contextvars(track_id=track_id)
    await _generate_for_track_id(track_id)


@broker.task
async def waveform_backfill_task() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Track.id)
            .where(
                Track.file_key.isnot(None),
                Track.is_active.is_(True),
                Track.waveform_data.is_(None),
            )
            .order_by(Track.id)
        )
        track_ids = [row[0] for row in result.all()]

    logger.info("waveform_backfill_started", total=len(track_ids))
    ok = 0
    for track_id in track_ids:
        if await _generate_for_track_id(track_id):
            ok += 1

    async with AsyncSessionLocal() as session:
        repo = AppSettingsRepository(session)
        await repo.upsert(
            key=_SETTING_KEY,
            value={"done": True, "processed": ok, "total": len(track_ids)},
            updated_by=None,
        )
        await session.commit()

    logger.info("waveform_backfill_done", processed=ok, total=len(track_ids))
