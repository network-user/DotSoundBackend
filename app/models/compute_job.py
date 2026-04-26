from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ComputeJob(Base, TimestampMixin):
    """Generic persistent compute-job queue.

    Survives backend and worker restarts. One row per
    (job_type, target_kind, target_id, feature_version) — repeat
    enqueue is a no-op. Workers claim with a lease deadline; if the
    lease expires the row is requeued.
    """

    __tablename__ = "compute_jobs"
    __table_args__ = (
        UniqueConstraint(
            "job_type",
            "target_kind",
            "target_id",
            "feature_version",
            name="uq_compute_job_target",
        ),
        Index(
            "ix_compute_jobs_claim",
            "status",
            "priority",
            "next_attempt_at",
        ),
        Index(
            "ix_compute_jobs_type_status",
            "job_type",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True
    )
    job_type: Mapped[str] = mapped_column(
        String(48), nullable=False
    )
    target_kind: Mapped[str | None] = mapped_column(
        String(24), nullable=True
    )
    target_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    feature_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="v1"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    claimed_by: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    result: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
