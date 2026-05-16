from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BackgroundJob(Base, TimestampMixin):
    """Unified accounting row for any Taskiq-driven background job.

    One row per ``enqueue()`` call. Middleware updates the row on
    start/finish/failure, so the admin panel sees a single timeline
    across all task names and queues. ``ComputeJob``/``LyricsJob``
    keep their own tables (pull-channel) — only terminal failures of
    those are mirrored here for the unified overview.
    """

    __tablename__ = "background_jobs"
    __table_args__ = (
        Index(
            "ix_background_jobs_status_created",
            "status",
            "created_at",
        ),
        Index("ix_background_jobs_name", "name"),
        Index("ix_background_jobs_queue", "queue"),
        Index(
            "ix_background_jobs_scheduled_job_id",
            "scheduled_job_id",
        ),
        Index(
            "ix_background_jobs_parent_job_id",
            "parent_job_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    queue: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="default"
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="queued"
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3"
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    parent_job_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    scheduled_job_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    taskiq_task_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
