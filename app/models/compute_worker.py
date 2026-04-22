from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ComputeWorker(Base, TimestampMixin):
    __tablename__ = "compute_workers"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    profile: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="cpu_light"
    )
    token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    suspended_reason: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    allowed_ip_cidrs: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    allowed_profiles: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    max_concurrent_jobs: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    suspended_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
