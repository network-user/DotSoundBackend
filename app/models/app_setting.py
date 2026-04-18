from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(
        String(96), primary_key=True
    )
    value: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
