"""Admin-facing API for audio-compute workers and routing."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_capability
from app.models.user import User
from app.services.audio_compute_admin_service import (
    AudioComputeAdminService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/audio-compute", tags=["admin"])


class WorkerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    #: The ``remote_whisper`` tier enqueues ``LyricsJob`` with
    # profile ``gpu_full`` (``lyrics_cascade.TIER_PROFILE_MAP``). A
    # worker with only ``cpu_light`` and no ``allowed_profiles``
    # for ``gpu_full`` never receives those ASR jobs (``claim`` 204).
    # ``profile=remote_whisper`` is accepted here and matched at
    # claim time to the same rows as ``gpu_full``.
    profile: str = Field(
        default="gpu_full",
        pattern=(
            r"^(cpu_light|gpu_full|catalog_only"
            r"|remote_whisper|speechkit_paid)$"
        ),
    )
    allowed_ip_cidrs: list[str] = Field(
        default_factory=list,
        max_length=64,
    )
    allowed_profiles: list[str] = Field(
        default_factory=list,
        max_length=8,
    )
    max_concurrent_jobs: int = Field(
        default=1,
        ge=1,
        le=32,
        description=(
            "Lyrics pull worker: while this many rows are ``running`` "
            "for this worker, ``/internal/audio-compute/jobs/claim`` "
            "returns 204 even when other ``queued`` jobs exist."
        ),
    )
    accept_open_allowlist: bool = False


class WorkerCreateResponse(BaseModel):
    id: str
    name: str
    profile: str
    secret: str
    allowed_ip_cidrs: list[str] = Field(default_factory=list)
    allowed_profiles: list[str] = Field(default_factory=list)
    max_concurrent_jobs: int = 1


class WorkerAllowlistRequest(BaseModel):
    allowed_ip_cidrs: list[str] = Field(
        default_factory=list,
        max_length=64,
    )
    allowed_profiles: list[str] | None = Field(
        default=None,
        max_length=8,
    )
    max_concurrent_jobs: int | None = Field(
        default=None, ge=1, le=32
    )
    accept_open_allowlist: bool = False


class RoutingModeRequest(BaseModel):
    mode: str = Field(
        pattern=(r"^(auto|force_local_cpu|force_remote_gpu" r"|disabled)$")
    )


@router.get("/workers")
async def list_workers(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("audio_compute.manage")),
) -> list[dict]:
    svc = AudioComputeAdminService(session)
    return await svc.list_workers()


@router.post("/workers", response_model=WorkerCreateResponse)
async def create_worker(
    body: WorkerCreateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("audio_compute.manage")),
) -> WorkerCreateResponse:
    svc = AudioComputeAdminService(session)
    try:
        data = await svc.create_worker(
            name=body.name,
            profile=body.profile,
            allowed_ip_cidrs=body.allowed_ip_cidrs,
            allowed_profiles=body.allowed_profiles or None,
            max_concurrent_jobs=body.max_concurrent_jobs,
            accept_open_allowlist=body.accept_open_allowlist,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=str(exc)
        ) from exc
    return WorkerCreateResponse(**data)


@router.patch("/workers/{worker_id}/allowlist")
async def update_worker_allowlist(
    worker_id: str,
    body: WorkerAllowlistRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("audio_compute.update_allowlist")
    ),
) -> dict:
    svc = AudioComputeAdminService(session)
    try:
        ok = await svc.update_worker_allowlist(
            worker_id=worker_id,
            allowed_ip_cidrs=body.allowed_ip_cidrs,
            allowed_profiles=body.allowed_profiles,
            max_concurrent_jobs=body.max_concurrent_jobs,
            accept_open_allowlist=(
                body.accept_open_allowlist
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=str(exc)
        ) from exc
    if not ok:
        raise HTTPException(status_code=404)
    return {"status": "ok"}


@router.post("/workers/{worker_id}/revoke")
async def revoke_worker(
    worker_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("audio_compute.manage")),
) -> dict:
    svc = AudioComputeAdminService(session)
    ok = await svc.revoke_worker(worker_id)
    if not ok:
        raise HTTPException(status_code=404)
    return {"status": "revoked"}


@router.delete("/workers/{worker_id}")
async def delete_revoked_worker(
    worker_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("audio_compute.manage")),
) -> dict:
    """Permanently remove a **revoked** worker row (UI housekeeping)."""
    svc = AudioComputeAdminService(session)
    result = await svc.delete_revoked_worker_row(
        worker_id
    )
    if result == "not_found":
        raise HTTPException(
            status_code=404, detail="worker not found"
        )
    if result == "not_revoked":
        raise HTTPException(
            status_code=400,
            detail="only_revoked_workers_can_be_removed",
        )
    return {"status": "deleted"}


@router.post("/workers/{worker_id}/rotate_secret")
async def rotate_worker_secret(
    worker_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("audio_compute.rotate_secret")),
) -> dict:
    svc = AudioComputeAdminService(session)
    new_secret = await svc.rotate_worker_secret(worker_id)
    if new_secret is None:
        raise HTTPException(status_code=404)
    return {
        "status": "rotated",
        "secret": new_secret,
    }


@router.get("/workers/{worker_id}/events")
async def list_worker_events(
    worker_id: str,
    limit: int = 100,
    _admin: User = Depends(
        require_capability("audio_compute.view_audit")
    ),
) -> dict:
    """Snapshot of last N events from the worker's Redis Stream."""
    from app.services.worker_event_stream import (
        fetch_recent,
    )

    clamped = max(1, min(500, int(limit)))
    events = await fetch_recent(
        worker_id, count=clamped
    )
    return {"worker_id": worker_id, "events": events}


@router.get("/workers/{worker_id}/jobs")
async def list_worker_jobs(
    worker_id: str,
    limit: int = 40,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> list[dict]:
    """Lyrics jobs assigned to this worker, with Redis progress
    for queued / running work.
    """
    svc = AudioComputeAdminService(session)
    data = await svc.list_worker_jobs(
        worker_id, limit=limit
    )
    if data is None:
        raise HTTPException(
            status_code=404, detail="worker not found"
        )
    return data


@router.get("/jobs")
async def list_jobs(
    session: AsyncSession = Depends(get_db),
    status_filter: str | None = None,
    sort: str = Query(
        "queue",
        pattern=r"^(queue|recent)$",
    ),
    _admin: User = Depends(require_capability("audio_compute.manage")),
) -> list[dict]:
    svc = AudioComputeAdminService(session)
    return await svc.list_jobs(
        status_filter=status_filter,
        sort=sort,
    )


class LyricsJobRoutingRequest(BaseModel):
    pinned_worker_id: str | None = Field(
        default=None,
        max_length=32,
    )
    queue_priority: int = Field(
        default=0,
        ge=-1_000_000,
        le=1_000_000,
    )


@router.patch("/jobs/{job_id}/routing")
async def patch_lyrics_job_routing(
    job_id: str,
    body: LyricsJobRoutingRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> dict:
    svc = AudioComputeAdminService(session)
    try:
        out = await svc.update_lyrics_job_routing(
            job_id,
            pinned_worker_id=body.pinned_worker_id,
            queue_priority=body.queue_priority,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    if out is None:
        raise HTTPException(status_code=404)
    return out


@router.get("/generic-compute-jobs")
async def list_generic_compute_jobs(
    session: AsyncSession = Depends(get_db),
    status: str | None = Query(None, max_length=16),
    limit: int = Query(100, ge=1, le=200),
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> list[dict]:
    svc = AudioComputeAdminService(session)
    return await svc.list_generic_compute_jobs(
        status=status,
        limit=limit,
    )


class GenericComputeJobRoutingRequest(BaseModel):
    pinned_worker_id: str | None = Field(
        default=None,
        max_length=32,
    )
    priority: int = Field(
        default=0,
        ge=-1_000_000,
        le=1_000_000,
    )
    release_claim: bool = False


@router.patch("/generic-compute-jobs/{job_id}/routing")
async def patch_generic_compute_job_routing(
    job_id: str,
    body: GenericComputeJobRoutingRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> dict:
    svc = AudioComputeAdminService(session)
    try:
        out = await svc.update_generic_compute_job_routing(
            job_id,
            pinned_worker_id=body.pinned_worker_id,
            priority=body.priority,
            release_claim=body.release_claim,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    if out is None:
        raise HTTPException(status_code=404)
    return out


class CancelByProgressRequest(BaseModel):
    progress_id: str = Field(
        min_length=16, max_length=64
    )


@router.post("/jobs/cancel-by-progress")
async def cancel_lyrics_job_by_progress(
    body: CancelByProgressRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> dict:
    """Cancel by ``progress_id`` from the Mini App / DevTools progress UI."""
    from app.repositories.audio_compute import (
        AudioComputeRepository,
    )
    from app.services.lyrics_job_cancel import (
        cancel_lyrics_job_for_admin,
    )

    repo = AudioComputeRepository(session)
    row = await repo.get_job_by_progress_id(
        body.progress_id.strip()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="job not found for this progress_id",
        )
    out = await cancel_lyrics_job_for_admin(
        session, row.id
    )
    if out is None:
        raise HTTPException(
            status_code=404, detail="job not found"
        )
    result = dict(out)
    result["job_id"] = row.id
    return result


@router.post("/operations/reap-expired-leases")
async def reap_expired_lyrics_leases(
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> dict:
    """Run lease reaper once: expired ``running`` jobs are advanced.

    For hosts without Taskiq running ``reap_expired_jobs_task`` each
    minute.
    """
    from app.tasks.audio_compute_reaper import (
        reap_once,
    )

    n = await reap_once()
    return {
        "status": "ok",
        "expired_leases_handled": int(n),
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_lyrics_compute_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("audio_compute.manage")
    ),
) -> dict:
    """Cancel a lyrics job (same as ``/tasks/lyrics-jobs/.../cancel``).

    Exposed here so **audio_compute.manage** operators can kill
    stuck ``running`` remote_whisper rows without **tasks.manage**.
    """
    from app.services.lyrics_job_cancel import (
        cancel_lyrics_job_for_admin,
    )

    out = await cancel_lyrics_job_for_admin(
        session, job_id
    )
    if out is None:
        raise HTTPException(
            status_code=404, detail="job not found"
        )
    return out


@router.get("/audit")
async def list_audit(
    session: AsyncSession = Depends(get_db),
    limit: int = 200,
    action_filter: str | None = None,
    _admin: User = Depends(require_capability("audio_compute.view_audit")),
) -> list[dict]:
    svc = AudioComputeAdminService(session)
    return await svc.list_audit(
        limit=limit, action_filter=action_filter
    )


@router.get("/routing")
async def get_routing(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("lyrics.routing")),
) -> dict:
    svc = AudioComputeAdminService(session)
    mode = await svc.get_routing_mode()
    return {"mode": mode}


@router.patch("/routing")
async def set_routing(
    body: RoutingModeRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("lyrics.routing")),
) -> dict:
    svc = AudioComputeAdminService(session)
    mode = await svc.set_routing_mode(body.mode)
    return {"status": "ok", "mode": mode}


class CascadeOrderRequest(BaseModel):
    cascade: list[str] = Field(
        max_length=8, default_factory=list
    )


@router.get("/cascade")
async def get_cascade(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("lyrics.routing")),
) -> dict:
    svc = AudioComputeAdminService(session)
    cascade = await svc.get_cascade_order()
    return {"cascade": cascade}


@router.patch("/cascade")
async def set_cascade(
    body: CascadeOrderRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("lyrics.routing")),
) -> dict:
    svc = AudioComputeAdminService(session)
    cascade = await svc.set_cascade_order(body.cascade)
    return {"cascade": cascade}


@router.get("/speechkit")
async def get_speechkit(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("lyrics.routing")),
) -> dict:
    svc = AudioComputeAdminService(session)
    return await svc.get_speechkit_status()


@router.post("/speechkit/reset_spent")
async def reset_speechkit_spent(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(
        require_capability("lyrics.routing")
    ),
) -> dict:
    svc = AudioComputeAdminService(session)
    return await svc.reset_speechkit_spent()
