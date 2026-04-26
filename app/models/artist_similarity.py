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
    from app.models.artist import Artist


class ArtistSimilarity(Base):
    __tablename__ = "artist_similarity"
    __table_args__ = (
        UniqueConstraint(
            "artist_id",
            "similar_artist_id",
            "feature_version",
            name="uq_artist_similarity_pair_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        autoincrement=True,
        primary_key=True,
    )
    artist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("artists.id", ondelete="CASCADE"),
        nullable=False,
    )
    similar_artist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("artists.id", ondelete="CASCADE"),
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

    artist: Mapped[Artist] = relationship(
        "Artist",
        foreign_keys=[artist_id],
    )
    similar_artist: Mapped[Artist] = relationship(
        "Artist",
        foreign_keys=[similar_artist_id],
    )
