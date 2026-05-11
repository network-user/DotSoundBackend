from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import BackgroundJob
from app.models.compute_job import ComputeJob
from app.models.lyrics_job import LyricsJob
from app.models.scheduled_job import ScheduledJob
from app.models.worker_audit import WorkerAuditLog


class AdminTasksRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_lyrics_job(self, job_id: str) -> LyricsJob | None:
        result = await self._session.execute(
            select(LyricsJob).where(LyricsJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_queued_lyrics_jobs(self) -> list[LyricsJob]:
        result = await self._session.execute(
            select(LyricsJob).where(LyricsJob.status == "queued")
        )
        return list(result.scalars().all())

    async def list_lyrics_jobs(
        self,
        *,
        status: str | None = None,
        profile: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[LyricsJob], int]:
        base = select(LyricsJob)
        count_q = select(func.count(LyricsJob.id))
        if status:
            base = base.where(LyricsJob.status == status)
            count_q = count_q.where(LyricsJob.status == status)
        if profile:
            base = base.where(LyricsJob.profile == profile)
            count_q = count_q.where(LyricsJob.profile == profile)
        rows_result = await self._session.execute(
            base.order_by(desc(LyricsJob.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list(rows_result.scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return rows, total

    async def list_compute_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[ComputeJob], int]:
        base = select(ComputeJob)
        count_q = select(func.count(ComputeJob.id))
        if status:
            base = base.where(ComputeJob.status == status)
            count_q = count_q.where(ComputeJob.status == status)
        if job_type:
            base = base.where(ComputeJob.job_type == job_type)
            count_q = count_q.where(ComputeJob.job_type == job_type)
        rows_result = await self._session.execute(
            base.order_by(ComputeJob.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list(rows_result.scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return rows, total

    async def list_worker_audit(
        self,
        *,
        worker_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkerAuditLog]:
        query = select(WorkerAuditLog)
        if worker_id:
            query = query.where(WorkerAuditLog.worker_id == worker_id)
        query = query.order_by(desc(WorkerAuditLog.created_at)).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_background_jobs_by_status(self) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(
                    BackgroundJob.status,
                    func.count(BackgroundJob.id),
                ).group_by(BackgroundJob.status)
            )
        ).all()
        return {status: int(count) for status, count in rows}

    async def count_compute_jobs_by_status(self) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(
                    ComputeJob.status,
                    func.count(ComputeJob.id),
                ).group_by(ComputeJob.status)
            )
        ).all()
        return {status: int(count) for status, count in rows}

    async def count_lyrics_jobs_by_status(self) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(
                    LyricsJob.status,
                    func.count(LyricsJob.id),
                ).group_by(LyricsJob.status)
            )
        ).all()
        return {status: int(count) for status, count in rows}

    async def list_upcoming_schedules(
        self, limit: int = 20
    ) -> list[ScheduledJob]:
        rows = (
            (
                await self._session.execute(
                    select(ScheduledJob)
                    .where(ScheduledJob.enabled.is_(True))
                    .order_by(ScheduledJob.next_run_at.asc().nulls_last())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def list_background_jobs(
        self,
        *,
        name: str | None = None,
        queue: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[BackgroundJob], int]:
        base = select(BackgroundJob)
        count_q = select(func.count(BackgroundJob.id))
        if name:
            base = base.where(BackgroundJob.name == name)
            count_q = count_q.where(BackgroundJob.name == name)
        if queue:
            base = base.where(BackgroundJob.queue == queue)
            count_q = count_q.where(BackgroundJob.queue == queue)
        if status:
            base = base.where(BackgroundJob.status == status)
            count_q = count_q.where(BackgroundJob.status == status)
        rows_result = await self._session.execute(
            base.order_by(desc(BackgroundJob.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list(rows_result.scalars().all())
        total = int((await self._session.execute(count_q)).scalar_one())
        return rows, total

    async def get_background_job(self, job_id: str) -> BackgroundJob | None:
        return await self._session.get(BackgroundJob, job_id)

    async def list_all_schedules(self) -> list[ScheduledJob]:
        rows = (
            (
                await self._session.execute(
                    select(ScheduledJob).order_by(ScheduledJob.name.asc())
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def get_schedule(self, schedule_id: str) -> ScheduledJob | None:
        return await self._session.get(ScheduledJob, schedule_id)

    async def find_schedule_by_name(self, name: str) -> ScheduledJob | None:
        result = await self._session.execute(
            select(ScheduledJob).where(ScheduledJob.name == name)
        )
        return result.scalar_one_or_none()

    async def add(self, row: ScheduledJob) -> None:
        self._session.add(row)

    async def delete(self, row: ScheduledJob) -> None:
        await self._session.delete(row)


__all__: Sequence[str] = ("AdminTasksRepository",)
