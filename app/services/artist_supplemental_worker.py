"""Taskiq worker for artist supplemental info enrichment.

Triggered automatically as a fallback when primary enrichment fails,
and can also be triggered manually. The provider is an opaque
dependency from dotsound_private_core.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from taskiq import TaskiqEvents, TaskiqState

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.repositories.app_settings import AppSettingsRepository
from app.repositories.artist_supplemental_info import (
    ArtistSupplementalInfoRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_AI_ARTIST_SUPPLEMENTAL_TTL_KEY = "ai.artist_supplemental_ttl_days"


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _preload_artist_supplemental_provider(
    _state: TaskiqState,
) -> None:
    try:
        from dotsound_private_core.services.artist_supplemental_provider import (
            warmup_artist_supplemental_provider,
        )
    except Exception:
        logger.info("artist_supplemental_provider_warmup_unavailable")
        return

    try:
        await asyncio.to_thread(warmup_artist_supplemental_provider)
        logger.info("artist_supplemental_provider_warmup_done")
    except Exception:
        logger.exception("artist_supplemental_provider_warmup_failed")


@broker.task
async def enrich_artist_supplemental_task(
    artist_id: int,
    force: bool = False,
) -> dict:
    import time

    structlog.contextvars.bind_contextvars(artist_id=artist_id)
    logger.info(
        "enrich_artist_supplemental_task_picked_up",
        artist_id=artist_id,
        force=force,
    )
    t_start = time.monotonic()
    async with AsyncSessionLocal() as session:
        repo = ArtistSupplementalInfoRepository(session)

        existing = await repo.get_by_artist_id(artist_id)
        if not force and existing and existing.status == "done" and existing.fetched_at:
            ttl = await _get_ttl(session)
            age = (datetime.now(UTC) - existing.fetched_at).days
            if age < ttl:
                logger.info(
                    "artist_supplemental_cached",
                    artist_id=artist_id,
                    age_days=age,
                )
                return {"status": "cached"}

        from sqlalchemy import select

        from app.models.artist import Artist

        result = await session.execute(
            select(Artist).where(Artist.id == artist_id)
        )
        artist = result.scalar_one_or_none()
        if artist is None:
            logger.warning("artist_supplemental_artist_not_found", artist_id=artist_id)
            return {"status": "not_found"}

        hints: dict = {}
        if artist.country:
            hints["country"] = artist.country
        if artist.bio:
            hints["bio_snippet"] = artist.bio[:200]

        try:
            from dotsound_private_core.services.artist_supplemental_provider import (
                fetch_artist_supplemental,
            )

            info = await asyncio.to_thread(
                fetch_artist_supplemental,
                name=artist.name,
                hints=hints,
            )
        except Exception:
            logger.exception(
                "artist_supplemental_provider_error", artist_id=artist_id
            )
            await repo.upsert(
                artist_id, status="failed", content=None, fetched_at=None
            )
            await session.commit()
            return {"status": "error"}

        if info is None or info.status == "not_found":
            await repo.upsert(
                artist_id,
                status="not_found",
                content=None,
                fetched_at=datetime.now(UTC),
            )
            await session.commit()
            logger.info("artist_supplemental_not_found", artist_id=artist_id)
            return {"status": "not_found"}

        content = (info.content or "")[:12_000]
        await repo.upsert(
            artist_id,
            status="done",
            content=content,
            fetched_at=datetime.now(UTC),
        )
        await session.commit()
        logger.info(
            "artist_supplemental_done",
            artist_id=artist_id,
            elapsed_s=round(time.monotonic() - t_start, 2),
            content_len=len(content),
        )
        return {"status": "done"}


async def _get_ttl(session) -> int:
    try:
        settings_repo = AppSettingsRepository(session)
        value = await settings_repo.get_value(_AI_ARTIST_SUPPLEMENTAL_TTL_KEY)
        if isinstance(value, dict) and "days" in value:
            days = int(value["days"])
            if days > 0:
                return days
    except Exception:
        pass
    return settings.artist_supplemental_ttl_days
