from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExperimentCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    arms: dict[str, int]
    description: str | None = Field(default=None, max_length=512)


class ExperimentUpdate(BaseModel):
    arms: dict[str, int] | None = None
    status: str | None = Field(default=None, max_length=16)
    description: str | None = Field(default=None, max_length=512)


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    arms: dict[str, int]
    status: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ExperimentArmStat(BaseModel):
    arm: str
    impressions: int
    completed: int
    skipped: int
    completion_rate: float
    skip_rate: float


class ExperimentSignificance(BaseModel):
    arm_a: str
    arm_b: str
    lift: float
    z: float
    p_value_two_sided: float
    sample_too_small: bool
    significant: bool


class ExperimentStats(BaseModel):
    experiment: ExperimentResponse
    assignment_counts: dict[str, int]
    arm_outcomes: list[ExperimentArmStat]
    significance: ExperimentSignificance | None = None
