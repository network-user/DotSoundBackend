from __future__ import annotations

import secrets as pysecrets
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.worker_audit import WorkerAuditLog
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services import compute_router
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def _serialize_worker(w: ComputeWorker) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "profile": w.profile,
        "active": w.active,
        "suspended_reason": w.suspended_reason,
        "last_seen_at": (
            w.last_seen_at.isoformat()
            if w.last_seen_at
            else None
        ),
        "last_ip": w.last_ip,
        "created_at": (
            w.created_at.isoformat()
            if w.created_at
            else None
        ),
    }


def _serialize_job(j: LyricsJob) -> dict[str, Any]:
    return {
        "id": j.id,
        "track_id": j.track_id,
        "status": j.status,
        "profile": j.profile,
        "routed_to_worker": j.routed_to_worker,
        "attempts": j.attempts,
        "duration_ms": j.duration_ms,
        "created_at": (
            j.created_at.isoformat()
            if j.created_at
            else None
        ),
        "finished_at": (
            j.finished_at.isoformat()
            if j.finished_at
            else None
        ),
    }


def _serialize_audit(r: WorkerAuditLog) -> dict[str, Any]:
    return {
        "id": r.id,
        "worker_id": r.worker_id,
        "ip": r.ip,
        "action": r.action,
        "job_id": r.job_id,
        "status_code": r.status_code,
        "meta": r.meta,
        "created_at": (
            r.created_at.isoformat()
            if r.created_at
            else None
        ),
    }


class AudioComputeAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AudioComputeRepository(session)

    async def list_workers(
        self,
    ) -> list[dict[str, Any]]:
        rows = await self._repo.list_workers()
        return [_serialize_worker(w) for w in rows]

    async def create_worker(
        self, name: str, profile: str
    ) -> dict[str, Any]:
        worker, secret = await cws.register_worker(
            self._session, name=name, profile=profile
        )
        await self._session.commit()
        logger.info(
            "compute_worker_created",
            worker_id=worker.id,
            profile=worker.profile,
        )
        return {
            "id": worker.id,
            "name": worker.name,
            "profile": worker.profile,
            "secret": secret,
        }

    async def revoke_worker(
        self, worker_id: str
    ) -> bool:
        affected = await self._repo.revoke_worker(
            worker_id
        )
        if affected == 0:
            return False
        await self._session.commit()
        return True

    async def rotate_worker_secret(
        self, worker_id: str
    ) -> str | None:
        new_secret = pysecrets.token_urlsafe(36)
        affected = await self._repo.update_worker_secret(
            worker_id, cws._hash_token(new_secret)
        )
        if affected == 0:
            return None
        await self._session.commit()
        return new_secret

    async def list_jobs(
        self,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = await self._repo.list_jobs(
            status_filter=status_filter, limit=200
        )
        return [_serialize_job(j) for j in rows]

    async def list_audit(
        self, limit: int = 200
    ) -> list[dict[str, Any]]:
        clamped = max(1, min(500, limit))
        rows = await self._repo.list_audit(
            limit=clamped
        )
        return [_serialize_audit(r) for r in rows]

    async def get_routing_mode(self) -> str:
        return await compute_router.get_routing_mode(
            self._session
        )

    async def set_routing_mode(self, mode: str) -> str:
        now = datetime.now(UTC)
        entry = await self._repo.get_routing_setting(
            compute_router.SETTING_ROUTING_MODE
        )
        if entry is None:
            entry = AppSetting(
                key=(
                    compute_router.SETTING_ROUTING_MODE
                ),
                value={"value": mode},
                updated_at=now,
            )
            self._repo.add(entry)
        else:
            entry.value = {"value": mode}
            entry.updated_at = now
        await self._session.commit()
        await compute_router.invalidate_settings_cache()
        logger.info("routing_mode_set", mode=mode)
        return mode
