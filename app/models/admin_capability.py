from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminCapability(Base):
    __tablename__ = "admin_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "capability",
            name="uq_admin_capability",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    capability: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    granted_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
