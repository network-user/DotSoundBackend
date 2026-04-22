"""Admin-facing API for audio-compute workers and routing."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
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
    profile: str = Field(
        pattern=(
            r"^(cpu_light|gpu_full|catalog_only"
            r"|remote_whisper|speechkit_paid)$"
        )
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
        default=1, ge=1, le=32
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


@router.get("/jobs")
async def list_jobs(
    session: AsyncSession = Depends(get_db),
    status_filter: str | None = None,
    _admin: User = Depends(require_capability("audio_compute.manage")),
) -> list[dict]:
    svc = AudioComputeAdminService(session)
    return await svc.list_jobs(status_filter=status_filter)


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
