from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecommendationImpression(Base):
    """One row per (user, track) shown on a recommendation surface.

    Captured at the moment recommendations are returned to the
    client. Tied to a `recommendation_id` so a downstream
    `ListenEvent` can join back to the impression and attribute
    listens to the algorithm version that surfaced the track.
    """

    __tablename__ = "recommendation_impressions"
    __table_args__ = (
        Index(
            "ix_rec_impressions_user_surface",
            "user_id",
            "surface",
            "created_at",
        ),
        Index(
            "ix_rec_impressions_recommendation_id",
            "recommendation_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    surface: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    recommendation_id: Mapped[str] = mapped_column(
        String(36), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
