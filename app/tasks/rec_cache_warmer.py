"""Recommendation-cache pre-warming tasks.

Warms ``rec:daily_mix:{user_id}``, ``rec:genre_mixes:{user_id}`` and
``rec:home:{user_id}`` for users who have been active in the last
``_ACTIVE_WINDOW_DAYS`` days, so the first request of each new day is
served from cache rather than triggering a full on-demand recalculation.

Intended cadence: once per day, shortly after midnight UTC (e.g. the
``seed_rec_cache_warmer_job`` scheduled-job row uses ``5 0 * * *``).

Architecture:
- ``dispatch_rec_cache_warmup_task`` — orchestrator; queries active
  user IDs and fans out one ``warm_user_rec_caches_task`` per user.
- ``warm_user_rec_caches_task`` — per-user worker; skips users whose
  caches are already warm (idempotent for the few minutes after midnight
  when TTLs expire one by one).
"""

from __future__ import annotations

import asyncio
import structlog
from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, select

from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.tkq import broker
from app.models.listen_event import ListenEvent

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ACTIVE_WINDOW_DAYS = 7
_DISPATCH_BATCH = 50
_WARM_CONCURRENCY = 4


async def _get_active_user_ids(days: int = _ACTIVE_WINDOW_DAYS) -> list[int]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(distinct(ListenEvent.user_id)).where(
                ListenEvent.created_at >= cutoff,
                ListenEvent.user_id.isnot(None),
            )
        )
        return list(result.scalars().all())


async def _warm_one(user_id: int) -> dict:
    redis = get_redis_client()
    mix_key = f"rec:daily_mix:{user_id}"
    genre_key = f"rec:genre_mixes:{user_id}"
    home_key = f"rec:home:{user_id}"

    mix_warm = bool(await redis.exists(mix_key))
    genre_warm = bool(await redis.exists(genre_key))
    home_warm = bool(await redis.exists(home_key))

    if mix_warm and genre_warm and home_warm:
        return {"user_id": user_id, "skipped": True}

    from app.services.recommendation_service import RecommendationService

    warmed: list[str] = []
    async with AsyncSessionLocal() as session:
        svc = RecommendationService(session)
        if not mix_warm:
            try:
                await svc.get_daily_mix(user_id)
                warmed.append("daily_mix")
            except Exception as exc:
                logger.warning(
                    "rec_warm_daily_mix_failed",
                    user_id=user_id,
                    error=str(exc),
                )
        if not genre_warm:
            try:
                await svc.get_genre_mixes(user_id)
                warmed.append("genre_mixes")
            except Exception as exc:
                logger.warning(
                    "rec_warm_genre_mixes_failed",
                    user_id=user_id,
                    error=str(exc),
                )
        if not home_warm:
            try:
                await svc.get_home_sections(user_id)
                warmed.append("home_sections")
            except Exception as exc:
                logger.warning(
                    "rec_warm_home_failed",
                    user_id=user_id,
                    error=str(exc),
                )

    return {"user_id": user_id, "warmed": warmed}


@broker.task
async def warm_user_rec_caches_task(user_id: int) -> dict:
    return await _warm_one(user_id)


@broker.task
async def dispatch_rec_cache_warmup_task(
    active_window_days: int = _ACTIVE_WINDOW_DAYS,
) -> dict:
    user_ids = await _get_active_user_ids(days=active_window_days)
    if not user_ids:
        logger.info("rec_cache_warmup_dispatch_no_users")
        return {"dispatched": 0, "total": 0}

    sem = asyncio.Semaphore(_WARM_CONCURRENCY)

    async def _dispatch_one(uid: int) -> None:
        async with sem:
            await warm_user_rec_caches_task.kiq(user_id=uid)

    for i in range(0, len(user_ids), _DISPATCH_BATCH):
        batch = user_ids[i : i + _DISPATCH_BATCH]
        await asyncio.gather(*[_dispatch_one(uid) for uid in batch])

    logger.info(
        "rec_cache_warmup_dispatched",
        total=len(user_ids),
    )
    return {"dispatched": len(user_ids)}


__all__ = [
    "dispatch_rec_cache_warmup_task",
    "warm_user_rec_caches_task",
]
