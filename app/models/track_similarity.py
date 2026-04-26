from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.track import Track


class TrackSimilarity(Base):
    __tablename__ = "track_similarity"
    __table_args__ = (
        UniqueConstraint(
            "track_id",
            "similar_track_id",
            "feature_version",
            name="uq_track_similarity_pair_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        autoincrement=True,
        primary_key=True,
    )
    track_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    similar_track_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason_tags: Mapped[list[Any] | None] = mapped_column(
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

    track: Mapped[Track] = relationship(
        "Track",
        foreign_keys=[track_id],
    )
    similar_track: Mapped[Track] = relationship(
        "Track",
        foreign_keys=[similar_track_id],
    )
