from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
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
