from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScheduledJob(Base, TimestampMixin):
    """Cron-driven schedule definition.

    The scheduler service polls enabled rows, evaluates ``cron``
    against ``last_run_at``, and kicks ``task_name`` via the
    unified ``enqueue()`` wrapper when due.
    """

    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index(
            "ix_scheduled_jobs_enabled_next_run",
            "enabled",
            "next_run_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(
        String(96), nullable=False, unique=True
    )
    task_name: Mapped[str] = mapped_column(
        String(96), nullable=False
    )
    queue: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="default"
    )
    cron: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(
        String(24), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    last_job_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
