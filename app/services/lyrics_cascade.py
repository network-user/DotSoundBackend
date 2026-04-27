"""Cascade orchestrator for lyrics jobs.

Single authority on tier transitions. Three callers:
- `LyricsService.trigger_auto_generation` for the initial dispatch
- `/api/v1/internal/audio-compute/jobs/{id}/fail` after a worker reports failure
- `app/tasks/audio_compute_reaper.reap_once` when a lease expires
- `AudioComputeAdminService.revoke_worker` to drain a revoked worker's queue

All decisions about *which* tier to attempt next live in
PrivateCore (`asr_policy.select_next_tier`). This module deals
with mutating `LyricsJob` state and enqueueing tasks; tier order
itself is immutable here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog  # noqa: F401  -- kept for explicit BoundLogger annotation
from dotsound_private_core.services.asr_policy import (
    DEFAULT_CASCADE,
    TIER_CATALOG_ONLY,
    TIER_REMOTE_WHISPER,
    TIER_SPEECHKIT_PAID,
    normalize_cascade,
    select_next_tier,
    should_use_paid_asr,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.models.lyrics_job import LyricsJob
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services.compute_router import (
    apply_speechkit_env_to_cascade,
)
from app.services.lyrics_worker import (
    set_lyrics_progress,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

TIER_PROFILE_MAP: dict[str, str] = {
    TIER_CATALOG_ONLY: TIER_CATALOG_ONLY,
    TIER_REMOTE_WHISPER: "gpu_full",
    TIER_SPEECHKIT_PAID: TIER_SPEECHKIT_PAID,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now().isoformat()


def _attempts(job: LyricsJob) -> list[dict[str, Any]]:
    raw = job.tier_attempts or []
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _spent_redis_key() -> str:
    bucket = _now().strftime("%Y%m")
    return f"speechkit_spent:{bucket}"


async def _get_monthly_speechkit_spent_rub() -> float:
    redis = get_redis_client()
    raw = await redis.get(_spent_redis_key())
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


async def _build_cascade(
    session: AsyncSession,
) -> tuple[str, ...]:
    """Read cascade order through `compute_router` (cached)."""
    from app.services.compute_router import (
        get_cascade_order,
    )

    return await get_cascade_order(session)


async def _dispatch_to_tier(
    session: AsyncSession,
    job: LyricsJob,
    tier: str,
    *,
    with_sync: bool,
    bypass_cache: bool,
) -> tuple[bool, str | None]:
    """Move ``job`` to ``tier`` and trigger any required work.

    Returns ``(dispatched, gating_reason)``. ``dispatched=False``
    means the tier itself refused (e.g. SpeechKit budget guard);
    the caller transitions to the next tier or fails the job.
    """
    profile = TIER_PROFILE_MAP.get(tier, tier)
    job.profile = profile
    job.current_tier = tier
    job.status = "queued"
    job.routed_to_worker = None
    job.started_at = None
    job.deadline_at = None

    attempts = _attempts(job)
    attempts.append(
        {
            "tier": tier,
            "started_at": _now_iso(),
            "status": "queued",
            "error": None,
        }
    )
    job.tier_attempts = attempts
    await session.flush()

    if tier in (TIER_REMOTE_WHISPER, TIER_SPEECHKIT_PAID):
        from app.models.track import Track

        t = await session.get(Track, job.track_id)
        if not t or not t.is_active:
            logger.warning(
                "tier_gated",
                tier=tier,
                job_id=job.id,
                reason="track_not_found",
            )
            return False, "track_not_found"
        if not (t.file_key or getattr(t, "sc_url", None)):
            logger.warning(
                "tier_gated",
                tier=tier,
                job_id=job.id,
                reason="no_track_audio",
            )
            return False, "no_track_audio"

    if tier == TIER_CATALOG_ONLY:
        from app.services.lyrics_worker import (
            catalog_only_lyrics_task,
        )

        task = await catalog_only_lyrics_task.kiq(
            track_id=job.track_id,
            with_sync=with_sync,
            progress_id=job.progress_id,
            bypass_cache=bypass_cache,
            job_id=job.id,
        )
        logger.info(
            "tier_dispatched",
            tier=tier,
            job_id=job.id,
            taskiq_id=task.task_id,
        )
        return True, None

    if tier == TIER_REMOTE_WHISPER:
        logger.info(
            "tier_dispatched",
            tier=tier,
            job_id=job.id,
            taskiq_id=None,
        )
        await set_lyrics_progress(
            job.progress_id,
            stage="queued",
            log_line=(
                "waiting for a remote compute worker"
            ),
            percent=15,
        )
        return True, None

    if tier == TIER_SPEECHKIT_PAID:
        spent = (
            await _get_monthly_speechkit_spent_rub()
        )
        ok, reason = should_use_paid_asr(
            enabled=settings.yandex_speechkit_enabled,
            monthly_spent_rub=spent,
            monthly_budget_rub=(
                settings.yandex_speechkit_monthly_budget_rub
            ),
            audio_seconds=0,
            rate_rub_per_minute=(
                settings.yandex_speechkit_rate_rub_per_minute
            ),
            soft_per_job_limit_rub=(
                settings.yandex_speechkit_soft_per_job_limit_rub
            ),
        )
        if not ok:
            logger.warning(
                "tier_gated",
                tier=tier,
                job_id=job.id,
                reason=reason,
            )
            return False, reason
        try:
            from app.services.lyrics_worker import (
                speechkit_lyrics_task,
            )

            task = await speechkit_lyrics_task.kiq(
                track_id=job.track_id,
                with_sync=with_sync,
                progress_id=job.progress_id,
                bypass_cache=bypass_cache,
                job_id=job.id,
            )
            logger.info(
                "tier_dispatched",
                tier=tier,
                job_id=job.id,
                taskiq_id=task.task_id,
            )
            return True, None
        except ImportError:
            logger.warning(
                "tier_dispatch_no_task",
                tier=tier,
                job_id=job.id,
            )
            return False, "speechkit_task_missing"

    logger.warning(
        "tier_unknown",
        tier=tier,
        job_id=job.id,
    )
    return False, "unknown_tier"


def _close_open_attempt(
    job: LyricsJob,
    *,
    status: str,
    error: str | None = None,
) -> None:
    attempts = _attempts(job)
    if not attempts:
        return
    last = attempts[-1]
    if last.get("status") in {"queued", "running"}:
        last["finished_at"] = _now_iso()
        last["status"] = status
        if error is not None:
            last["error"] = (error or "")[:512]
    job.tier_attempts = attempts


async def start_cascade(
    session: AsyncSession,
    *,
    job: LyricsJob,
    with_sync: bool,
    bypass_cache: bool,
) -> str:
    """Initial dispatch for a freshly created LyricsJob.

    Decides the cascade order, stores it on the job, and tries
    each tier in turn until one accepts the work or the cascade
    is exhausted (in which case the job is marked failed).
    Returns the *active* tier the job is now sitting in.
    """
    cascade = await _build_cascade(session)
    job.tiers_planned = list(cascade)
    job.tier_attempts = []
    await session.flush()
    return await _advance_to_next_tier(
        session,
        job=job,
        with_sync=with_sync,
        bypass_cache=bypass_cache,
        previous_status="queued",
        previous_error=None,
    )


async def _advance_to_next_tier(
    session: AsyncSession,
    *,
    job: LyricsJob,
    with_sync: bool,
    bypass_cache: bool,
    previous_status: str,
    previous_error: str | None,
) -> str:
    from app.core.observability import (
        lyrics_job_observed,
        tier_fallback_observed,
    )

    if job.tiers_planned:
        _base = normalize_cascade(job.tiers_planned)
    else:
        _base = DEFAULT_CASCADE
    cascade = apply_speechkit_env_to_cascade(_base)
    previous_tier = job.current_tier
    root_cause: str | None = previous_error
    if previous_status != "queued":
        _close_open_attempt(
            job,
            status=previous_status,
            error=previous_error,
        )
    while True:
        attempts = _attempts(job)
        next_tier = select_next_tier(attempts, cascade)
        if next_tier is None:
            job.status = "failed"
            job.finished_at = _now()
            detail: str
            if (
                root_cause
                and previous_error
                and root_cause != previous_error
            ):
                detail = f"{root_cause} | then: {previous_error}"
            else:
                detail = (
                    previous_error
                    or root_cause
                    or "all tiers failed"
                )
            if len(detail) > 1800:
                detail = detail[:1800] + "..."
            job.error = detail[:1024]
            await session.flush()
            await set_lyrics_progress(
                job.progress_id,
                stage="error",
                terminal_state="error",
                log_line="cascade exhausted: " + detail,
            )
            logger.error(
                "cascade_exhausted",
                job_id=job.id,
                attempted=[
                    item.get("tier") for item in attempts
                ],
                last_error=previous_error,
                root_cause=root_cause,
            )
            duration = 0.0
            if job.started_at is not None:
                started_aware = job.started_at
                if started_aware.tzinfo is None:
                    started_aware = (
                        started_aware.replace(
                            tzinfo=UTC
                        )
                    )
                duration = (
                    _now() - started_aware
                ).total_seconds()
            lyrics_job_observed(
                tier=previous_tier or "unknown",
                status="cascade_exhausted",
                duration_seconds=duration,
            )
            return "exhausted"
        ok, reason = await _dispatch_to_tier(
            session,
            job,
            next_tier,
            with_sync=with_sync,
            bypass_cache=bypass_cache,
        )
        if ok:
            await session.flush()
            if (
                previous_tier
                and previous_tier != next_tier
            ):
                tier_fallback_observed(
                    from_tier=previous_tier,
                    to_tier=next_tier,
                    reason=(
                        previous_error or previous_status
                    ),
                )
            return next_tier
        _close_open_attempt(
            job,
            status="gated",
            error=reason or "tier_gated",
        )
        previous_error = reason or "tier_gated"


async def handle_tier_failure(
    session: AsyncSession,
    *,
    job: LyricsJob,
    reason: str,
    with_sync: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Move ``job`` to the next tier after ``reason`` failed it.

    Returns True if a transition happened (caller should NOT
    mark_job_failed); False if the cascade was exhausted (caller
    should write the terminal failure).
    """
    next_tier = await _advance_to_next_tier(
        session,
        job=job,
        with_sync=with_sync,
        bypass_cache=bypass_cache,
        previous_status="failed",
        previous_error=reason,
    )
    return next_tier != "exhausted"


async def handle_tier_miss(
    session: AsyncSession,
    *,
    job: LyricsJob,
    reason: str = "no_lyrics_found",
    with_sync: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Tier finished cleanly but didn't produce anything (e.g.
    catalog cascade returned None). Same flow as `handle_tier_failure`
    but the audit message reads ``status=miss`` rather than ``fail``.
    """
    next_tier = await _advance_to_next_tier(
        session,
        job=job,
        with_sync=with_sync,
        bypass_cache=bypass_cache,
        previous_status="miss",
        previous_error=reason,
    )
    return next_tier != "exhausted"


async def handle_lease_expired(
    session: AsyncSession,
    *,
    job: LyricsJob,
    with_sync: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Reaper entrypoint. Identical to a tier failure but the
    reason is fixed so admins can filter on it.
    """
    return await handle_tier_failure(
        session,
        job=job,
        reason="lease_expired",
        with_sync=with_sync,
        bypass_cache=bypass_cache,
    )


async def fallback_jobs_for_revoked_worker(
    session: AsyncSession,
    *,
    worker_id: str,
) -> int:
    """Drain in-flight jobs from a revoked worker into the next
    cascade tier. Returns the number of jobs touched.
    """
    repo = AudioComputeRepository(session)
    rows = await repo.list_running_jobs_for_worker(
        worker_id
    )
    if not rows:
        return 0
    for job in rows:
        await handle_tier_failure(
            session,
            job=job,
            reason=f"worker_revoked:{worker_id}",
        )
    return len(rows)


__all__ = [
    "TIER_CATALOG_ONLY",
    "TIER_REMOTE_WHISPER",
    "TIER_SPEECHKIT_PAID",
    "TIER_PROFILE_MAP",
    "fallback_jobs_for_revoked_worker",
    "handle_lease_expired",
    "handle_tier_failure",
    "handle_tier_miss",
    "start_cascade",
]
