from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob


class ComputeJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_status_for_track(
        self, *, track_id: int, job_type: str
    ) -> str | None:
        result = await self._session.execute(
            select(ComputeJob.status)
            .where(
                ComputeJob.target_kind == "track",
                ComputeJob.target_id == str(track_id),
                ComputeJob.job_type == job_type,
            )
            .limit(1)
        )
        value = result.scalar_one_or_none()
        return value if isinstance(value, str) else None
