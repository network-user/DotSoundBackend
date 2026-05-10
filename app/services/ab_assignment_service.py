"""A/B assignment service.

Resolves a deterministic arm for a (user, experiment) pair using
the opaque assignment hash from PrivateCore. Caches the assignment
in ``experiment_assignments`` so replays survive arm-share edits.
"""

from __future__ import annotations

import structlog
from dotsound_private_core.services.ab_policy import (
    ABAssignment,
    assign_arm,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import (
    Experiment,
    ExperimentAssignment,
)

EXPERIMENT_STATUS_RUNNING = "running"
EXPERIMENT_STATUS_DRAFT = "draft"
EXPERIMENT_STATUS_PAUSED = "paused"
EXPERIMENT_STATUS_COMPLETED = "completed"

logger = structlog.get_logger(__name__)


class ABAssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_assignment(
        self,
        *,
        experiment_key: str,
        user_id: int,
    ) -> ABAssignment | None:
        experiment = await self._load_running(experiment_key)
        if experiment is None:
            return None
        cached = await self._load_cached(
            experiment_id=experiment.id, user_id=user_id
        )
        if cached is not None:
            return ABAssignment(
                experiment_key=experiment_key,
                arm=cached.arm,
                bucket=cached.bucket,
            )
        arms_dict = self._coerce_arms(experiment.arms)
        if not arms_dict:
            return None
        assignment = assign_arm(
            experiment_key=experiment_key,
            user_id=user_id,
            arms=arms_dict,
        )
        if assignment is None:
            return None
        await self._persist_assignment(
            experiment_id=experiment.id,
            user_id=user_id,
            assignment=assignment,
        )
        return assignment

    async def _load_running(self, experiment_key: str) -> Experiment | None:
        result = await self._session.execute(
            select(Experiment).where(
                Experiment.key == experiment_key,
                Experiment.status == EXPERIMENT_STATUS_RUNNING,
            )
        )
        return result.scalar_one_or_none()

    async def _load_cached(
        self,
        *,
        experiment_id: int,
        user_id: int,
    ) -> ExperimentAssignment | None:
        result = await self._session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment_id,
                ExperimentAssignment.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _persist_assignment(
        self,
        *,
        experiment_id: int,
        user_id: int,
        assignment: ABAssignment,
    ) -> None:
        row = ExperimentAssignment(
            experiment_id=experiment_id,
            user_id=user_id,
            arm=assignment.arm,
            bucket=assignment.bucket,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()

    @staticmethod
    def _coerce_arms(raw: object) -> dict[str, int]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, int] = {}
        for k, v in raw.items():
            try:
                share = int(v)
            except (TypeError, ValueError):
                continue
            if share > 0:
                out[str(k)] = share
        return out
