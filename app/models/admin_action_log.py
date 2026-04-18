from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminActionLog(Base):
    __tablename__ = "admin_actions_log"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    target_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    target_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    meta: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
