from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.track import Track


class GenreSample(Base):
    __tablename__ = "genre_samples"
    __table_args__ = (
        UniqueConstraint(
            "genre",
            "track_id",
            name="uq_genre_samples_genre_track",
        ),
        Index(
            "ix_genre_samples_genre_position",
            "genre",
            "position",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    genre: Mapped[str] = mapped_column(String(64), nullable=False)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    curated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    track: Mapped[Track] = relationship(
        "Track",
    )
