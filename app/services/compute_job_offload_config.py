from __future__ import annotations

from dotsound_private_core.services.compute_job_policy import (
    RoutingMode,
    get_job_rule,
    requires_worker,
)

from app.config import settings
from app.services import compute_queue_service as q


def configured_compute_offload_job_types() -> frozenset[str]:
    raw = (settings.compute_offload_job_types or "").strip()
    if not raw:
        return frozenset()
    out: set[str] = set()
    for line in raw.splitlines():
        for piece in line.split(","):
            job_type = q.canonical_job_type(piece.strip())
            if job_type in q.OFFLOADABLE_JOB_TYPES:
                out.add(job_type)
    return frozenset(out)


def worker_claim_enabled(job_type: str) -> bool:
    canonical_type = q.canonical_job_type(job_type)
    if canonical_type not in q.OFFLOADABLE_JOB_TYPES:
        return False
    if canonical_type == q.JOB_SOUNDCLOUD_RPC:
        return bool(settings.sc_offload_enabled)
    if requires_worker(canonical_type):
        return True
    if settings.compute_offload_enabled:
        return True
    return canonical_type in configured_compute_offload_job_types()


def should_enqueue_remote(
    job_type: str,
    *,
    force_local: bool = False,
    force_offload: bool = False,
) -> bool:
    canonical_type = q.canonical_job_type(job_type)
    rule = get_job_rule(canonical_type)
    if force_local:
        return requires_worker(canonical_type)
    if force_offload:
        return canonical_type in q.OFFLOADABLE_JOB_TYPES
    if requires_worker(canonical_type):
        return True
    if rule.routing is not RoutingMode.PREFER_WORKER:
        return False
    return worker_claim_enabled(canonical_type)


__all__ = [
    "configured_compute_offload_job_types",
    "should_enqueue_remote",
    "worker_claim_enabled",
]
