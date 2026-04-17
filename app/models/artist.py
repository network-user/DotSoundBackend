from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Artist(Base, TimestampMixin):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(256), nullable=False
    )
    name_normalized: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True
    )
    image_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(20), server_default="internal", nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    bio: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    birth_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    birthplace: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    country: Mapped[str | None] = mapped_column(
        String(2), nullable=True
    )
    website_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    enrichment_status: Mapped[str] = mapped_column(
        String(16),
        server_default="pending",
        nullable=False,
        index=True,
    )
    enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    track_links: Mapped[list[TrackArtist]] = relationship(
        back_populates="artist",
        cascade="all, delete-orphan",
    )


class TrackArtist(Base):
    __tablename__ = "track_artists"
    __table_args__ = (
        UniqueConstraint(
            "track_id",
            "artist_id",
            name="uq_track_artist",
        ),
        Index(
            "ix_track_artists_artist_id",
            "artist_id",
        ),
    )

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        server_default="primary",
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )

    artist: Mapped[Artist] = relationship(
        back_populates="track_links",
    )
