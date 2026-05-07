"""Push/pull control-plane signals for pull-based compute workers.

Queues admin-driven job cancellation tokens in Redis per worker so
``/workers/heartbeat`` can return them alongside claim-pause flags.

Transports only; policy for *when* to enqueue lives in callers
(``lyrics_job_cancel`` etc.).
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from app.config import settings
from app.core.redis import get_redis_client
from app.models.compute_worker import ComputeWorker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

CANCEL_SIGNAL_PREFIX = "worker:cancel_signals:"
_SIGNAL_TTL_SECONDS = 48 * 3600
_MAX_CANCEL_POP = 48


def worker_claims_blocked(
    worker: ComputeWorker,
    *,
    now: datetime | None = None,
) -> bool:
    dt = now or datetime.now(UTC)
    pu = worker.claims_paused_until
    if pu is None:
        return False
    if pu.tzinfo is None:
        pu = pu.replace(tzinfo=UTC)
    return pu > dt


def _cancel_key(worker_id: str) -> str:
    return f"{CANCEL_SIGNAL_PREFIX}{worker_id}"


async def enqueue_cancel_signals(
    worker_id: str | None,
    job_ids: list[str],
) -> None:
    if not worker_id or not job_ids:
        return
    redis = get_redis_client()
    key = _cancel_key(worker_id)
    cleaned = [j for j in job_ids if isinstance(j, str) and j][:100]
    if not cleaned:
        return
    pipe = redis.pipeline()
    for jid in cleaned:
        pipe.rpush(key, jid)
    pipe.expire(key, _SIGNAL_TTL_SECONDS)
    await pipe.execute()
    logger.info(
        "worker_cancel_signals_enqueued",
        worker_id=worker_id,
        count=len(cleaned),
    )


async def pop_cancel_signals(worker_id: str) -> list[str]:
    redis = get_redis_client()
    key = _cancel_key(worker_id)
    out: list[str] = []
    for _ in range(_MAX_CANCEL_POP):
        raw = await redis.lpop(key)
        if raw is None:
            break
        s = (
            raw.decode("utf-8", errors="ignore")
            if isinstance(raw, bytes)
            else str(raw)
        )
        if s and s not in out:
            out.append(s)
    return out


def _parse_semver_tuple(
    v: str,
) -> tuple[int, ...]:
    parts = []
    for chunk in (v or "").strip().split(".")[:4]:
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            continue
        try:
            parts.append(int(digits))
        except ValueError:
            continue
    return tuple(parts)


def package_version_below_min(
    reported: str | None,
    minimum: str | None,
) -> bool:
    floor = (minimum or "").strip()
    if not floor:
        return False
    parsed_rep = _parse_semver_tuple(str(reported or ""))
    parsed_min = _parse_semver_tuple(floor)
    if not parsed_rep or not parsed_min:
        return False
    ln = max(len(parsed_rep), len(parsed_min))
    a = list(parsed_rep) + [0] * (ln - len(parsed_rep))
    b = list(parsed_min) + [0] * (ln - len(parsed_min))
    return tuple(a) < tuple(b)


def build_heartbeat_control(
    *,
    worker: ComputeWorker,
    cancel_job_ids: list[str],
) -> dict[str, object]:
    now = datetime.now(UTC)
    claims_paused = worker_claims_blocked(worker, now=now)
    min_v = str(settings.compute_worker_min_package_version or "").strip()
    low = package_version_below_min(
        worker.worker_package_version,
        min_v,
    )
    return {
        "claims_paused": claims_paused,
        "claims_pause_reason": worker.claims_pause_reason,
        "claims_paused_until": (
            worker.claims_paused_until.isoformat()
            if worker.claims_paused_until
            else None
        ),
        "cancel_job_ids": cancel_job_ids,
        "min_worker_package_version": min_v,
        "worker_package_version_below_min": low,
    }


async def merge_heartbeat_control_payload(
    worker: ComputeWorker,
    *,
    package_version_header: str | None,
) -> dict[str, object]:
    pkg = (package_version_header or "").strip()[:32]
    if pkg:
        worker.worker_package_version = pkg
    cans = await pop_cancel_signals(worker.id)
    return build_heartbeat_control(
        worker=worker,
        cancel_job_ids=cans,
    )


__all__ = [
    "build_heartbeat_control",
    "enqueue_cancel_signals",
    "merge_heartbeat_control_payload",
    "package_version_below_min",
    "pop_cancel_signals",
    "worker_claims_blocked",
]
