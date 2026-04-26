from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.artist import Artist


class ArtistFeatures(Base):
    __tablename__ = "artist_features"

    artist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("artists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    centroid_vector: Mapped[list[Any] | dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    dominant_moods: Mapped[list[Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    style_tags: Mapped[list[Any] | None] = mapped_column(
        JSON,
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

    artist: Mapped[Artist] = relationship(
        "Artist",
        foreign_keys=[artist_id],
    )
