from __future__ import annotations

from dotsound_private_core.services.ab_policy import (
    ProportionStats,
    two_proportion_z_test,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.user import User
from app.repositories.experiment import (
    ExperimentRepository,
)
from app.schemas.experiment import (
    ExperimentArmStat,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentSignificance,
    ExperimentStats,
    ExperimentUpdate,
)
from app.services.ab_assignment_service import (
    EXPERIMENT_STATUS_COMPLETED,
    EXPERIMENT_STATUS_DRAFT,
    EXPERIMENT_STATUS_PAUSED,
    EXPERIMENT_STATUS_RUNNING,
)

router = APIRouter(
    prefix="/recsys/experiments",
    tags=["admin-recsys-experiments"],
)

_ALLOWED_STATUSES = {
    EXPERIMENT_STATUS_DRAFT,
    EXPERIMENT_STATUS_RUNNING,
    EXPERIMENT_STATUS_PAUSED,
    EXPERIMENT_STATUS_COMPLETED,
}


def _arm_rates(
    counts: dict[str, int],
) -> ExperimentArmStat:
    impressions = max(0, int(counts.get("impressions", 0)))
    completed = max(0, int(counts.get("completed", 0)))
    skipped = max(0, int(counts.get("skipped", 0)))
    completion_rate = completed / impressions if impressions > 0 else 0.0
    skip_rate = skipped / impressions if impressions > 0 else 0.0
    return ExperimentArmStat(
        arm="",
        impressions=impressions,
        completed=completed,
        skipped=skipped,
        completion_rate=completion_rate,
        skip_rate=skip_rate,
    )


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> list[ExperimentResponse]:
    repo = ExperimentRepository(session)
    return [
        ExperimentResponse.model_validate(row) for row in await repo.list_all()
    ]


@router.post("", response_model=ExperimentResponse)
async def create_experiment(
    body: ExperimentCreate,
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
    repo = ExperimentRepository(session)
    if await repo.get_by_key(body.key) is not None:
        raise HTTPException(
            status_code=409,
            detail="experiment key already exists",
        )
    if not body.arms or sum(body.arms.values()) <= 0:
        raise HTTPException(
            status_code=400,
            detail="arms must contain at least one positive share",
        )
    row = await repo.create(
        key=body.key,
        arms=body.arms,
        description=body.description,
    )
    return ExperimentResponse.model_validate(row)


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: int,
    body: ExperimentUpdate,
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
    if body.status is not None and body.status not in _ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(_ALLOWED_STATUSES)}",
        )
    if body.arms is not None and sum(body.arms.values()) <= 0:
        raise HTTPException(
            status_code=400,
            detail="arms must contain at least one positive share",
        )
    repo = ExperimentRepository(session)
    row = await repo.update(
        experiment_id,
        arms=body.arms,
        status=body.status,
        description=body.description,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return ExperimentResponse.model_validate(row)


@router.delete("/{experiment_id}")
async def delete_experiment(
    experiment_id: int,
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    repo = ExperimentRepository(session)
    deleted = await repo.delete(experiment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="experiment not found")
    return {"deleted": True}


@router.get("/{experiment_id}/stats", response_model=ExperimentStats)
async def experiment_stats(
    experiment_id: int,
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> ExperimentStats:
    repo = ExperimentRepository(session)
    experiment = await repo.get_by_id(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    counts = await repo.assignment_counts(experiment_id)
    algo_versions = [
        f"{experiment.key}:{arm}" for arm in (experiment.arms or {}).keys()
    ]
    outcomes = await repo.listen_outcomes_per_arm(
        experiment_id=experiment_id,
        algorithm_version_arms=algo_versions,
    )
    arm_stats: list[ExperimentArmStat] = []
    arm_to_outcome: dict[str, dict[str, int]] = {}
    for algo_v, bucket in outcomes.items():
        arm_name = algo_v.split(":", 1)[-1]
        arm_to_outcome[arm_name] = bucket
        item = _arm_rates(bucket)
        arm_stats.append(item.model_copy(update={"arm": arm_name}))

    significance: ExperimentSignificance | None = None
    arms_sorted = sorted(arm_to_outcome.keys())
    if len(arms_sorted) >= 2:
        a_name, b_name = arms_sorted[0], arms_sorted[1]
        a_bucket = arm_to_outcome[a_name]
        b_bucket = arm_to_outcome[b_name]
        result = two_proportion_z_test(
            ProportionStats(
                arm=a_name,
                successes=int(a_bucket.get("completed", 0)),
                trials=int(a_bucket.get("impressions", 0)),
            ),
            ProportionStats(
                arm=b_name,
                successes=int(b_bucket.get("completed", 0)),
                trials=int(b_bucket.get("impressions", 0)),
            ),
        )
        significance = ExperimentSignificance(
            arm_a=result.arm_a,
            arm_b=result.arm_b,
            lift=result.lift,
            z=result.z,
            p_value_two_sided=result.p_value_two_sided,
            sample_too_small=result.sample_too_small,
            significant=result.significant,
        )

    return ExperimentStats(
        experiment=ExperimentResponse.model_validate(experiment),
        assignment_counts=counts,
        arm_outcomes=arm_stats,
        significance=significance,
    )
