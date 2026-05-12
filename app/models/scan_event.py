from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    verdict: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )
    threat_name: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    scan_mode: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    __table_args__ = (
        Index("ix_scan_events_verdict_scanned_at", "verdict", "scanned_at"),
    )
