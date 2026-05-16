from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog
from dotsound_private_core.services.compute_job_policy import (
    RoutingMode,
    get_job_rule,
    requires_worker,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

LocalComputeHandler = Callable[
    ["LocalComputeJob"],
    Awaitable[dict[str, Any] | None],
]


@dataclass(frozen=True, slots=True)
class LocalComputeJob:
    job_type: str
    target_kind: str | None
    target_id: str | None
    payload: dict[str, Any]
    feature_version: str

    @classmethod
    def from_model(cls, job: ComputeJob) -> LocalComputeJob:
        payload = job.payload if isinstance(job.payload, dict) else {}
        return cls(
            job_type=q.canonical_job_type(job.job_type),
            target_kind=job.target_kind,
            target_id=job.target_id,
            payload=payload,
            feature_version=job.feature_version,
        )


@dataclass(frozen=True, slots=True)
class ComputeDispatchResult:
    status: str
    job_id: str | None = None
    result: dict[str, Any] | None = None


def _offload_enabled(job_type: str) -> bool:
    if job_type == q.JOB_SOUNDCLOUD_RPC:
        return bool(settings.sc_offload_enabled)
    return bool(settings.compute_offload_enabled)


async def dispatch_compute_job(
    session: AsyncSession,
    *,
    job_type: str,
    target_kind: str | None = None,
    target_id: str | int | None = None,
    payload: dict[str, Any] | None = None,
    feature_version: str = q.DEFAULT_FEATURE_VERSION,
    local_handler: LocalComputeHandler | None = None,
    force_local: bool = False,
    force_offload: bool = False,
) -> ComputeDispatchResult:
    canonical_type = q.canonical_job_type(job_type)
    rule = get_job_rule(canonical_type)
    target_id_str = None if target_id is None else str(target_id)
    local_job = LocalComputeJob(
        job_type=canonical_type,
        target_kind=target_kind,
        target_id=target_id_str,
        payload=payload or {},
        feature_version=feature_version,
    )
    should_enqueue = (
        force_offload
        or (
            not force_local
            and rule.routing
            in (RoutingMode.PREFER_WORKER, RoutingMode.WORKER_ONLY)
            and _offload_enabled(canonical_type)
        )
        or (requires_worker(canonical_type) and not force_local)
    )
    if should_enqueue:
        job = await q.enqueue(
            session,
            job_type=canonical_type,
            target_kind=target_kind,
            target_id=target_id_str,
            payload=payload or {},
            feature_version=feature_version,
            priority=q.default_priority(canonical_type),
            max_attempts=q.default_max_attempts(canonical_type),
        )
        await session.flush()
        logger.info(
            "compute_job_dispatched_remote",
            job_id=job.id,
            job_type=job.job_type,
            target_kind=job.target_kind,
            target_id=job.target_id,
        )
        return ComputeDispatchResult(status="queued", job_id=job.id)

    if local_handler is None:
        raise ValueError(f"local_compute_handler_missing:{canonical_type}")
    result = await local_handler(local_job)
    logger.info(
        "compute_job_dispatched_local",
        job_type=canonical_type,
        target_kind=target_kind,
        target_id=target_id_str,
    )
    return ComputeDispatchResult(
        status="local",
        result=result or {"status": "ok"},
    )


__all__ = [
    "ComputeDispatchResult",
    "LocalComputeHandler",
    "LocalComputeJob",
    "dispatch_compute_job",
]
