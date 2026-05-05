from __future__ import annotations

import asyncio
import secrets as pysecrets
from datetime import UTC, datetime
from typing import Any

import structlog
from dotsound_private_core.services.network_policy import (
    is_open_allowlist,
    normalize_cidrs,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.worker_audit import WorkerAuditLog
from app.repositories.audio_compute import (
    AudioComputeRepository,
)
from app.services import compute_queue_service as cq
from app.services import compute_router
from app.services import compute_worker_service as cws

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_MAX_QUEUE_PRIORITY = 1_000_000


def _serialize_worker(w: ComputeWorker) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "profile": w.profile,
        "active": w.active,
        "suspended_reason": w.suspended_reason,
        "suspended_until": (
            w.suspended_until.isoformat()
            if w.suspended_until
            else None
        ),
        "revoked_at": (
            w.revoked_at.isoformat()
            if w.revoked_at
            else None
        ),
        "allowed_ip_cidrs": w.allowed_ip_cidrs or [],
        "allowed_profiles": w.allowed_profiles or [],
        "max_concurrent_jobs": w.max_concurrent_jobs,
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
        "progress_id": j.progress_id,
        "track_id": j.track_id,
        "status": j.status,
        "profile": j.profile,
        "current_tier": j.current_tier,
        "tiers_planned": j.tiers_planned or [],
        "tier_attempts": j.tier_attempts or [],
        "routed_to_worker": j.routed_to_worker,
        "pinned_worker_id": j.pinned_worker_id,
        "queue_priority": j.queue_priority,
        "attempts": j.attempts,
        "duration_ms": j.duration_ms,
        "error": j.error,
        "deadline_at": (
            j.deadline_at.isoformat()
            if j.deadline_at
            else None
        ),
        "started_at": (
            j.started_at.isoformat()
            if j.started_at
            else None
        ),
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


def _open_allowlist_includes_ipv6(
    cidrs: list[str],
) -> list[str]:
    """``0.0.0.0/0`` only matches **IPv4**; IPv6 clients (common with
    ngrok / some egress paths) need ``::/0`` as well. When the admin
    preset is "any IP" we only store the v4 default route — append
    ``::/0`` so :func:`is_ip_in_cidrs` can match v6 source addresses
    in :func:`verify_worker_request`.
    """
    if not cidrs or not is_open_allowlist(cidrs):
        return cidrs
    if "::/0" in cidrs or "0.0.0.0/0" not in cidrs:
        return cidrs
    return normalize_cidrs(
        [
            *cidrs,
            "::/0",
        ]
    )


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
        self,
        name: str,
        profile: str,
        allowed_ip_cidrs: list[str] | None = None,
        allowed_profiles: list[str] | None = None,
        max_concurrent_jobs: int = 1,
        accept_open_allowlist: bool = False,
    ) -> dict[str, Any]:
        normalized_cidrs = (
            normalize_cidrs(allowed_ip_cidrs)
            if allowed_ip_cidrs
            else []
        )
        normalized_cidrs = (
            _open_allowlist_includes_ipv6(
                normalized_cidrs
            )
        )
        if (
            normalized_cidrs
            and is_open_allowlist(normalized_cidrs)
            and not accept_open_allowlist
        ):
            raise ValueError("open_allowlist_requires_accept")
        normalized_profiles = (
            [p for p in allowed_profiles if p]
            if allowed_profiles
            else None
        )
        worker, secret = await cws.register_worker(
            self._session,
            name=name,
            profile=profile,
            allowed_ip_cidrs=normalized_cidrs or None,
            allowed_profiles=normalized_profiles,
            max_concurrent_jobs=max_concurrent_jobs,
        )
        await self._session.commit()
        logger.info(
            "compute_worker_created",
            worker_id=worker.id,
            profile=worker.profile,
            allowed_cidrs_count=len(normalized_cidrs),
            open_allowlist=is_open_allowlist(
                normalized_cidrs
            ),
        )
        return {
            "id": worker.id,
            "name": worker.name,
            "profile": worker.profile,
            "secret": secret,
            "allowed_ip_cidrs": normalized_cidrs,
            "allowed_profiles": normalized_profiles or [],
            "max_concurrent_jobs": worker.max_concurrent_jobs,
        }

    async def update_worker_allowlist(
        self,
        worker_id: str,
        allowed_ip_cidrs: list[str] | None,
        allowed_profiles: list[str] | None = None,
        max_concurrent_jobs: int | None = None,
        accept_open_allowlist: bool = False,
    ) -> bool:
        normalized_cidrs = (
            normalize_cidrs(allowed_ip_cidrs)
            if allowed_ip_cidrs
            else None
        )
        if normalized_cidrs is not None:
            normalized_cidrs = (
                _open_allowlist_includes_ipv6(
                    normalized_cidrs
                )
            )
        if (
            normalized_cidrs
            and is_open_allowlist(normalized_cidrs)
            and not accept_open_allowlist
        ):
            raise ValueError("open_allowlist_requires_accept")
        affected = (
            await self._repo.update_worker_allowlist(
                worker_id,
                normalized_cidrs,
                allowed_profiles,
                max_concurrent_jobs,
            )
        )
        if affected == 0:
            return False
        await self._session.commit()
        logger.info(
            "compute_worker_allowlist_updated",
            worker_id=worker_id,
            allowed_cidrs_count=(
                len(normalized_cidrs)
                if normalized_cidrs
                else 0
            ),
        )
        return True

    async def revoke_worker(
        self, worker_id: str
    ) -> bool:
        affected = await self._repo.revoke_worker(
            worker_id
        )
        if affected == 0:
            return False
        await self._session.commit()
        await cws.invalidate_worker_nonces(worker_id)
        try:
            from app.services.lyrics_cascade import (
                fallback_jobs_for_revoked_worker,
            )

            await fallback_jobs_for_revoked_worker(
                self._session, worker_id=worker_id
            )
        except ImportError:
            pass
        logger.info(
            "compute_worker_revoked",
            worker_id=worker_id,
        )
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
        await cws.invalidate_worker_nonces(worker_id)
        logger.info(
            "compute_worker_secret_rotated",
            worker_id=worker_id,
        )
        return new_secret

    async def delete_revoked_worker_row(
        self, worker_id: str
    ) -> str:
        w = await self._repo.get_worker(
            worker_id
        )
        if w is None:
            return "not_found"
        if w.revoked_at is None:
            return "not_revoked"
        await cws.invalidate_worker_nonces(
            worker_id
        )
        n = await self._repo.delete_revoked_worker(
            worker_id
        )
        if n == 0:
            return "not_found"
        await self._session.commit()
        logger.info(
            "compute_worker_row_deleted",
            worker_id=worker_id,
        )
        return "deleted"

    async def list_jobs(
        self,
        status_filter: str | None = None,
        sort: str = "queue",
    ) -> list[dict[str, Any]]:
        sm = "queue" if sort == "queue" else "recent"
        rows = await self._repo.list_jobs(
            status_filter=status_filter,
            limit=200,
            sort=sm,
        )
        return [_serialize_job(j) for j in rows]

    async def update_lyrics_job_routing(
        self,
        job_id: str,
        *,
        pinned_worker_id: str | None,
        queue_priority: int,
    ) -> dict[str, Any] | None:
        job = await self._repo.get_job(job_id)
        if job is None:
            return None
        if job.status not in {"queued", "running"}:
            raise ValueError("job_not_routable")
        qp = max(
            -_MAX_QUEUE_PRIORITY,
            min(_MAX_QUEUE_PRIORITY, int(queue_priority)),
        )
        if pinned_worker_id:
            w = await self._repo.get_worker(
                pinned_worker_id
            )
            if (
                w is None
                or w.revoked_at is not None
                or not w.active
            ):
                raise ValueError("worker_not_found")
            if not cws.worker_can_run_lyrics_profile(
                w, job.profile
            ):
                raise ValueError("worker_profile_mismatch")
        from app.services.lyrics_cascade import (
            reassign_remote_lyrics_job,
        )

        await reassign_remote_lyrics_job(
            self._session,
            job=job,
            pinned_worker_id=pinned_worker_id or None,
            queue_priority=qp,
        )
        await cws._log_audit(
            self._session,
            worker_id=pinned_worker_id,
            ip=None,
            action="admin_job_routing",
            job_id=job.id,
            status_code=200,
            meta={
                "queue_priority": qp,
                "pinned_worker_id": pinned_worker_id,
            },
        )
        await self._session.commit()
        logger.info(
            "lyrics_job_routing_updated",
            job_id=job.id,
            pinned_worker_id=pinned_worker_id,
            queue_priority=qp,
        )
        return _serialize_job(job)

    async def list_generic_compute_jobs(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from app.models.compute_job import ComputeJob

        sm = max(1, min(200, int(limit)))
        stmt = select(ComputeJob)
        if status:
            stmt = stmt.where(ComputeJob.status == status)
        stmt = (
            stmt.order_by(
                ComputeJob.priority.desc(),
                ComputeJob.created_at.desc(),
            ).limit(sm)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return [
            {
                "id": r.id,
                "job_type": r.job_type,
                "target_kind": r.target_kind,
                "target_id": r.target_id,
                "status": r.status,
                "priority": r.priority,
                "pinned_worker_id": r.pinned_worker_id,
                "claimed_by": r.claimed_by,
                "attempts": r.attempts,
                "last_error": r.last_error,
                "created_at": (
                    r.created_at.isoformat()
                    if r.created_at
                    else None
                ),
            }
            for r in rows
        ]

    async def update_generic_compute_job_routing(
        self,
        job_id: str,
        *,
        pinned_worker_id: str | None,
        priority: int,
        release_claim: bool,
    ) -> dict[str, Any] | None:
        from app.models.compute_job import ComputeJob

        job = await self._session.get(
            ComputeJob, job_id
        )
        if job is None:
            return None
        if job.status in cq.TERMINAL_STATUSES:
            raise ValueError("job_terminal")
        pr = max(
            -_MAX_QUEUE_PRIORITY,
            min(_MAX_QUEUE_PRIORITY, int(priority)),
        )
        if pinned_worker_id:
            w = await self._repo.get_worker(
                pinned_worker_id
            )
            if (
                w is None
                or w.revoked_at is not None
                or not w.active
            ):
                raise ValueError("worker_not_found")
        job.pinned_worker_id = pinned_worker_id or None
        job.priority = pr
        if release_claim and job.status == cq.STATUS_CLAIMED:
            job.status = cq.STATUS_PENDING
            job.claimed_by = None
            job.claimed_at = None
            job.claim_deadline_at = None
            job.started_at = None
        await self._session.flush()
        await cws._log_audit(
            self._session,
            worker_id=pinned_worker_id,
            ip=None,
            action="admin_compute_job_routing",
            job_id=job.id,
            status_code=200,
            meta={
                "priority": pr,
                "release_claim": bool(release_claim),
            },
        )
        await self._session.commit()
        logger.info(
            "generic_compute_job_routing_updated",
            job_id=job.id,
        )
        return {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "priority": job.priority,
            "pinned_worker_id": job.pinned_worker_id,
            "claimed_by": job.claimed_by,
        }

    async def list_worker_jobs(
        self,
        worker_id: str,
        limit: int = 40,
    ) -> list[dict[str, Any]] | None:
        w = await self._repo.get_worker(
            worker_id
        )
        if w is None:
            return None
        from app.services.lyrics_worker import (
            get_lyrics_progress,
        )

        sm = max(1, min(200, int(limit)))
        rows = await self._repo.list_jobs_for_worker(
            worker_id, limit=sm
        )
        in_flight: frozenset[str] = frozenset(
            ("queued", "running")
        )

        async def with_progress(
            j: LyricsJob,
        ) -> dict[str, Any]:
            d = _serialize_job(j)
            d["progress_id"] = j.progress_id
            if j.status in in_flight:
                d["lyrics_progress"] = (
                    await get_lyrics_progress(
                        j.progress_id
                    )
                )
            else:
                d["lyrics_progress"] = None
            return d

        if not rows:
            return []
        return await asyncio.gather(
            *(with_progress(j) for j in rows)
        )

    async def list_audit(
        self,
        limit: int = 200,
        action_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        clamped = max(1, min(500, limit))
        rows = await self._repo.list_audit(
            limit=clamped,
            action_filter=action_filter,
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

    async def get_cascade_order(self) -> list[str]:
        cascade = (
            await compute_router.get_cascade_order(
                self._session
            )
        )
        return list(cascade)

    async def set_cascade_order(
        self, cascade: list[str]
    ) -> list[str]:
        from dotsound_private_core.services.asr_policy import (
            normalize_cascade,
        )

        normalized = list(normalize_cascade(cascade))
        now = datetime.now(UTC)
        entry = await self._repo.get_routing_setting(
            compute_router.SETTING_CASCADE_ORDER
        )
        if entry is None:
            entry = AppSetting(
                key=(
                    compute_router.SETTING_CASCADE_ORDER
                ),
                value={"value": normalized},
                updated_at=now,
            )
            self._repo.add(entry)
        else:
            entry.value = {"value": normalized}
            entry.updated_at = now
        await self._session.commit()
        await compute_router.invalidate_settings_cache()
        logger.info(
            "cascade_order_set", cascade=normalized
        )
        return normalized

    async def get_speechkit_status(self) -> dict[str, Any]:
        from app.config import settings as app_settings
        from app.services.asr_speechkit_adapter import (
            get_monthly_spent_rub,
        )

        spent = await get_monthly_spent_rub()
        budget = float(
            app_settings.yandex_speechkit_monthly_budget_rub
        )
        return {
            "enabled": bool(
                app_settings.yandex_speechkit_enabled
            ),
            "monthly_budget_rub": budget,
            "monthly_spent_rub": float(spent),
            "remaining_rub": max(0.0, budget - spent),
            "rate_rub_per_minute": float(
                app_settings.yandex_speechkit_rate_rub_per_minute
            ),
            "soft_per_job_limit_rub": float(
                app_settings.yandex_speechkit_soft_per_job_limit_rub
            ),
            "api_key_set": bool(
                app_settings.yandex_speechkit_api_key
            ),
        }

    async def reset_speechkit_spent(self) -> dict[str, Any]:
        from app.services.asr_speechkit_adapter import (
            reset_monthly_spent,
        )

        await reset_monthly_spent()
        logger.warning(
            "speechkit_spent_reset_by_admin"
        )
        return await self.get_speechkit_status()
