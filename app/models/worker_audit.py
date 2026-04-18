from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkerAuditLog(Base):
    __tablename__ = "worker_audit_log"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    job_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    status_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    meta: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
