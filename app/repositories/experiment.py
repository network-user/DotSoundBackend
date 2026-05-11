from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import (
    Experiment,
    ExperimentAssignment,
)
from app.models.listen_event import ListenEvent
from app.models.recommendation_impression import (
    RecommendationImpression,
)


class ExperimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, experiment_id: int) -> Experiment | None:
        return await self._session.get(Experiment, experiment_id)

    async def get_by_key(self, key: str) -> Experiment | None:
        result = await self._session.execute(
            select(Experiment).where(Experiment.key == key)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Experiment]:
        result = await self._session.execute(
            select(Experiment).order_by(Experiment.id.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        key: str,
        arms: dict[str, int],
        description: str | None = None,
    ) -> Experiment:
        row = Experiment(
            key=key,
            arms=arms,
            description=description,
            status="draft",
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(
        self,
        experiment_id: int,
        *,
        arms: dict[str, int] | None = None,
        status: str | None = None,
        description: str | None = None,
    ) -> Experiment | None:
        row = await self.get_by_id(experiment_id)
        if row is None:
            return None
        if arms is not None:
            row.arms = arms
        if status is not None:
            row.status = status
        if description is not None:
            row.description = description
        await self._session.flush()
        return row

    async def delete(self, experiment_id: int) -> bool:
        row = await self.get_by_id(experiment_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def assignment_counts(self, experiment_id: int) -> dict[str, int]:
        result = await self._session.execute(
            select(
                ExperimentAssignment.arm,
                func.count().label("c"),
            )
            .where(ExperimentAssignment.experiment_id == experiment_id)
            .group_by(ExperimentAssignment.arm)
        )
        return {str(arm): int(count) for arm, count in result.all()}

    async def listen_outcomes_per_arm(
        self,
        *,
        experiment_id: int,
        algorithm_version_arms: Iterable[str],
        surfaces: Iterable[str] | None = None,
    ) -> dict[str, dict[str, int]]:
        impressions = (
            select(
                ListenEvent.user_id,
                ListenEvent.track_id,
                ListenEvent.completed,
                ListenEvent.skipped,
                RecommendationImpression.algorithm_version,
            )
            .join(
                RecommendationImpression,
                (ListenEvent.track_id == RecommendationImpression.track_id)
                & (ListenEvent.user_id == RecommendationImpression.user_id),
            )
            .where(
                RecommendationImpression.algorithm_version.in_(
                    list(algorithm_version_arms)
                )
            )
        )
        if surfaces:
            impressions = impressions.where(
                RecommendationImpression.surface.in_(list(surfaces))
            )
        rows = (await self._session.execute(impressions)).all()
        out: dict[str, dict[str, int]] = {}
        for _user_id, _track_id, completed, skipped, algo_v in rows:
            arm_bucket = out.setdefault(
                str(algo_v),
                {"impressions": 0, "completed": 0, "skipped": 0},
            )
            arm_bucket["impressions"] += 1
            if completed:
                arm_bucket["completed"] += 1
            if skipped:
                arm_bucket["skipped"] += 1
        return out
