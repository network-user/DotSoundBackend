from datetime import UTC, datetime

from sqlalchemy import case, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.models.worker_audit import WorkerAuditLog


class AudioComputeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_workers(
        self,
    ) -> list[ComputeWorker]:
        result = await self._session.execute(
            select(ComputeWorker).order_by(
                ComputeWorker.created_at.desc()
            )
        )
        return list(result.scalars().all())

    async def get_worker(
        self, worker_id: str
    ) -> ComputeWorker | None:
        result = await self._session.execute(
            select(ComputeWorker).where(
                ComputeWorker.id == worker_id
            )
        )
        return result.scalar_one_or_none()

    async def revoke_worker(
        self, worker_id: str
    ) -> int:
        result = await self._session.execute(
            update(ComputeWorker)
            .where(ComputeWorker.id == worker_id)
            .values(
                active=False,
                suspended_reason="revoked",
                revoked_at=datetime.now(UTC),
            )
            .execution_options(
                synchronize_session="fetch"
            )
        )
        return int(result.rowcount or 0)

    async def delete_revoked_worker(
        self, worker_id: str
    ) -> int:
        """Remove a **revoked** row from ``compute_workers`` only
        (housekeeping; jobs keep ``routed_to_worker`` as history).
        """
        result = await self._session.execute(
            delete(ComputeWorker).where(
                ComputeWorker.id == worker_id,
                ComputeWorker.revoked_at.isnot(None),
            )
        )
        return int(result.rowcount or 0)

    async def update_worker_secret(
        self, worker_id: str, token_hash: str
    ) -> int:
        result = await self._session.execute(
            update(ComputeWorker)
            .where(ComputeWorker.id == worker_id)
            .values(
                token_hash=token_hash,
                suspended_reason=None,
                active=True,
                suspended_until=None,
            )
            .execution_options(
                synchronize_session="fetch"
            )
        )
        return int(result.rowcount or 0)

    async def update_worker_allowlist(
        self,
        worker_id: str,
        allowed_ip_cidrs: list[str] | None,
        allowed_profiles: list[str] | None = None,
        max_concurrent_jobs: int | None = None,
    ) -> int:
        values: dict[str, object] = {
            "allowed_ip_cidrs": allowed_ip_cidrs,
        }
        if allowed_profiles is not None:
            values["allowed_profiles"] = allowed_profiles
        if max_concurrent_jobs is not None:
            values["max_concurrent_jobs"] = max(
                1, int(max_concurrent_jobs)
            )
        result = await self._session.execute(
            update(ComputeWorker)
            .where(ComputeWorker.id == worker_id)
            .values(**values)
            .execution_options(
                synchronize_session="fetch"
            )
        )
        return int(result.rowcount or 0)

    async def suspend_worker_until(
        self,
        worker_id: str,
        until: datetime,
        reason: str | None = None,
    ) -> int:
        result = await self._session.execute(
            update(ComputeWorker)
            .where(ComputeWorker.id == worker_id)
            .values(
                suspended_until=until,
                suspended_reason=reason,
            )
            .execution_options(
                synchronize_session="fetch"
            )
        )
        return int(result.rowcount or 0)

    async def list_jobs(
        self,
        status_filter: str | None = None,
        limit: int = 200,
        sort: str = "recent",
    ) -> list[LyricsJob]:
        stmt = select(LyricsJob)
        if status_filter:
            stmt = stmt.where(
                LyricsJob.status == status_filter
            )
        if sort == "queue":
            queue_rank = case(
                (LyricsJob.status == "queued", 0),
                (LyricsJob.status == "running", 1),
                else_=2,
            )
            stmt = (
                stmt.order_by(
                    queue_rank.asc(),
                    LyricsJob.queue_priority.desc(),
                    LyricsJob.created_at.asc(),
                ).limit(limit)
            )
        else:
            stmt = (
                stmt.order_by(
                    LyricsJob.created_at.desc()
                ).limit(limit)
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_jobs_for_worker(
        self,
        worker_id: str,
        limit: int = 40,
    ) -> list[LyricsJob]:
        """Jobs this worker is / was working on
        (``routed_to_worker``), newest first.
        """
        sm = max(1, min(200, int(limit)))
        result = await self._session.execute(
            select(LyricsJob)
            .where(
                LyricsJob.routed_to_worker
                == worker_id
            )
            .order_by(
                LyricsJob.updated_at.desc()
            )
            .limit(sm)
        )
        return list(result.scalars().all())

    async def get_job(
        self, job_id: str
    ) -> LyricsJob | None:
        result = await self._session.execute(
            select(LyricsJob).where(LyricsJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_job_by_progress_id(
        self, progress_id: str
    ) -> LyricsJob | None:
        result = await self._session.execute(
            select(LyricsJob).where(
                LyricsJob.progress_id == progress_id
            )
        )
        return result.scalar_one_or_none()

    async def get_job_for_worker(
        self, job_id: str, worker_id: str
    ) -> LyricsJob | None:
        result = await self._session.execute(
            select(LyricsJob).where(
                LyricsJob.id == job_id,
                LyricsJob.routed_to_worker == worker_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_running_jobs_for_worker(
        self, worker_id: str
    ) -> list[LyricsJob]:
        result = await self._session.execute(
            select(LyricsJob).where(
                LyricsJob.routed_to_worker == worker_id,
                LyricsJob.status == "running",
            )
        )
        return list(result.scalars().all())

    async def list_expired_running_jobs(
        self, now: datetime, limit: int = 50
    ) -> list[LyricsJob]:
        result = await self._session.execute(
            select(LyricsJob)
            .where(
                LyricsJob.status == "running",
                LyricsJob.deadline_at.is_not(None),
                LyricsJob.deadline_at < now,
            )
            .order_by(LyricsJob.deadline_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_track_file_key(
        self, track_id: int
    ) -> str | None:
        result = await self._session.execute(
            select(Track.file_key).where(
                Track.id == track_id
            )
        )
        row = result.first()
        return row[0] if row else None

    async def list_audit(
        self,
        limit: int = 200,
        action_filter: str | None = None,
    ) -> list[WorkerAuditLog]:
        stmt = (
            select(WorkerAuditLog)
            .order_by(
                WorkerAuditLog.created_at.desc()
            )
            .limit(limit)
        )
        if action_filter:
            stmt = stmt.where(
                WorkerAuditLog.action == action_filter
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def prune_audit_older_than(
        self, cutoff: datetime
    ) -> int:
        result = await self._session.execute(
            delete(WorkerAuditLog).where(
                WorkerAuditLog.created_at < cutoff
            )
        )
        return int(result.rowcount or 0)

    async def get_routing_setting(
        self, key: str
    ) -> AppSetting | None:
        stmt = await self._session.execute(
            select(AppSetting).where(
                AppSetting.key == key
            )
        )
        return stmt.scalar_one_or_none()

    def add(self, entity: object) -> None:
        self._session.add(entity)
