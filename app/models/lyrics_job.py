from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LyricsJob(Base, TimestampMixin):
    __tablename__ = "lyrics_jobs"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True
    )
    track_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    progress_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    requested_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    profile: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="cpu_light"
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="queued"
    )
    routed_to_worker: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    audio_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
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
