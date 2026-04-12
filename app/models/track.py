from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.album import Album
    from app.models.complaint import Complaint
    from app.models.lyrics import TrackLyrics


class Track(Base, TimestampMixin):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(256), index=True, nullable=False
    )
    artist: Mapped[str | None] = mapped_column(
        String(256), index=True, nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    genre: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(20), server_default="active", nullable=False
    )
    file_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    play_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    cover_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        type_=BigInteger,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(20), server_default="internal", nullable=False
    )
    video_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    sc_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sc_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    hls_manifest_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
    album_id: Mapped[int | None] = mapped_column(
        ForeignKey("albums.id", ondelete="SET NULL"),
        nullable=True,
    )
    comments_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )

    complaints: Mapped[list[Complaint]] = relationship(
        back_populates="track",
        cascade="all, delete-orphan",
    )
    lyrics: Mapped[TrackLyrics | None] = relationship(
        back_populates="track",
        uselist=False,
        cascade="all, delete-orphan",
    )
    album: Mapped[Album | None] = relationship(
        back_populates="tracks",
    )
