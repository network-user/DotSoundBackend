from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.track import Track


class TrackPreviewClip(Base):
    __tablename__ = "track_preview_clips"
    __table_args__ = (
        CheckConstraint(
            "source IN ('fixed_offset','content_based')",
            name="ck_track_preview_clips_source",
        ),
    )

    track_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    start_sec: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0"
    )
    duration_sec: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="15"
    )
    source: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="fixed_offset",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    track: Mapped[Track] = relationship("Track", foreign_keys=[track_id])
