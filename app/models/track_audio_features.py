from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.track import Track


class TrackAudioFeatures(Base):
    __tablename__ = "track_audio_features"

    track_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    feature_vector: Mapped[list[Any] | dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    mood_tags: Mapped[list[Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    tempo_bpm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    energy: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    highlight_start_sec: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    feature_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="v1",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    track: Mapped[Track] = relationship(
        "Track",
        foreign_keys=[track_id],
    )
