"""Admin-facing API for audio-compute workers and routing."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.dependencies import get_db, require_capability
from app.models.app_setting import AppSetting
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.worker_audit import WorkerAuditLog
from app.services import compute_router
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

router = APIRouter(
    prefix="/audio-compute", tags=["admin"]
)


class WorkerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    profile: str = Field(pattern=r"^(cpu_light|gpu_full)$")


class WorkerCreateResponse(BaseModel):
    id: str
    name: str
    profile: str
    secret: str


class RoutingModeRequest(BaseModel):
    mode: str = Field(
        pattern=r"^(auto|force_local_cpu|force_remote_gpu|disabled)$"
    )


@router.get("/workers")
async def list_workers(
    session: AsyncSession = Depends(get_db),
    _=Depends(require_capability("audio_compute.manage")),
) -> list[dict]:
    result = await session.execute(
        select(ComputeWorker).order_by(
            ComputeWorker.created_at.desc()
        )
    )
    rows = result.scalars().all()
    return [
        {
            "id": w.id,
            "name": w.name,
            "profile": w.profile,
            "active": w.active,
            "suspended_reason": w.suspended_reason,
            "last_seen_at": w.last_seen_at.isoformat()
            if w.last_seen_at
            else None,
            "last_ip": w.last_ip,
            "created_at": w.created_at.isoformat()
            if w.created_at
            else None,
        }
        for w in rows
    ]


@router.post(
    "/workers", response_model=WorkerCreateResponse
)
async def create_worker(
    body: WorkerCreateRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_capability("audio_compute.manage")),
) -> WorkerCreateResponse:
    worker, secret = await cws.register_worker(
        session, name=body.name, profile=body.profile
    )
    await session.commit()
    logger.info(
        "compute_worker_created",
        worker_id=worker.id,
        profile=worker.profile,
    )
    return WorkerCreateResponse(
        id=worker.id,
        name=worker.name,
        profile=worker.profile,
        secret=secret,
    )


@router.post("/workers/{worker_id}/revoke")
async def revoke_worker(
    worker_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_capability("audio_compute.manage")),
) -> dict:
    result = await session.execute(
        update(ComputeWorker)
        .where(ComputeWorker.id == worker_id)
        .values(
            active=False, suspended_reason="revoked"
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404)
    await session.commit()
    return {"status": "revoked"}


@router.post("/workers/{worker_id}/rotate_secret")
async def rotate_worker_secret(
    worker_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(
        require_capability("audio_compute.rotate_secret")
    ),
) -> dict:
    import secrets as pysecrets

    new_secret = pysecrets.token_urlsafe(36)
    result = await session.execute(
        update(ComputeWorker)
        .where(ComputeWorker.id == worker_id)
        .values(
            token_hash=cws._hash_token(new_secret),
            suspended_reason=None,
            active=True,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404)
    await session.commit()
    return {"status": "rotated", "secret": new_secret}


@router.get("/jobs")
async def list_jobs(
    session: AsyncSession = Depends(get_db),
    status_filter: str | None = None,
    _=Depends(require_capability("audio_compute.manage")),
) -> list[dict]:
    stmt = select(LyricsJob).order_by(
        LyricsJob.created_at.desc()
    ).limit(200)
    if status_filter:
        stmt = stmt.where(
            LyricsJob.status == status_filter
        )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": j.id,
            "track_id": j.track_id,
            "status": j.status,
            "profile": j.profile,
            "routed_to_worker": j.routed_to_worker,
            "attempts": j.attempts,
            "duration_ms": j.duration_ms,
            "created_at": j.created_at.isoformat()
            if j.created_at
            else None,
            "finished_at": j.finished_at.isoformat()
            if j.finished_at
            else None,
        }
        for j in rows
    ]


@router.get("/audit")
async def list_audit(
    session: AsyncSession = Depends(get_db),
    limit: int = 200,
    _=Depends(
        require_capability("audio_compute.view_audit")
    ),
) -> list[dict]:
    limit = max(1, min(500, limit))
    result = await session.execute(
        select(WorkerAuditLog)
        .order_by(WorkerAuditLog.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "worker_id": r.worker_id,
            "ip": r.ip,
            "action": r.action,
            "job_id": r.job_id,
            "status_code": r.status_code,
            "meta": r.meta,
            "created_at": r.created_at.isoformat()
            if r.created_at
            else None,
        }
        for r in rows
    ]


@router.get("/routing")
async def get_routing(
    session: AsyncSession = Depends(get_db),
    _=Depends(require_capability("lyrics.routing")),
) -> dict:
    mode = await compute_router.get_routing_mode(session)
    return {"mode": mode}


@router.patch("/routing")
async def set_routing(
    body: RoutingModeRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_capability("lyrics.routing")),
) -> dict:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    stmt = await session.execute(
        select(AppSetting).where(
            AppSetting.key
            == compute_router.SETTING_ROUTING_MODE
        )
    )
    entry = stmt.scalar_one_or_none()
    if entry is None:
        entry = AppSetting(
            key=compute_router.SETTING_ROUTING_MODE,
            value={"value": body.mode},
            updated_at=now,
        )
        session.add(entry)
    else:
        entry.value = {"value": body.mode}
        entry.updated_at = now
    await session.commit()
    await compute_router.invalidate_settings_cache()
    logger.info(
        "routing_mode_set", mode=body.mode
    )
    return {"status": "ok", "mode": body.mode}
