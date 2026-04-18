from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.compute_worker import ComputeWorker
from app.models.lyrics_job import LyricsJob
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

    async def revoke_worker(
        self, worker_id: str
    ) -> int:
        result = await self._session.execute(
            update(ComputeWorker)
            .where(ComputeWorker.id == worker_id)
            .values(
                active=False,
                suspended_reason="revoked",
            )
            .execution_options(
                synchronize_session="fetch"
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
    ) -> list[LyricsJob]:
        stmt = (
            select(LyricsJob)
            .order_by(LyricsJob.created_at.desc())
            .limit(limit)
        )
        if status_filter:
            stmt = stmt.where(
                LyricsJob.status == status_filter
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_audit(
        self, limit: int = 200
    ) -> list[WorkerAuditLog]:
        result = await self._session.execute(
            select(WorkerAuditLog)
            .order_by(
                WorkerAuditLog.created_at.desc()
            )
            .limit(limit)
        )
        return list(result.scalars().all())

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
