from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class TrackPlaybackFailureEvent(Base):
    __tablename__ = "track_playback_failure_events"
    __table_args__ = (
        Index(
            "ix_track_playback_failure_events_track_id_created",
            "track_id",
            "created_at",
        ),
        Index(
            "ix_track_playback_failure_events_source_created",
            "source",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail_truncated: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
