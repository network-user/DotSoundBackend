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
    from app.models.track_info import TrackInfo


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
    catalog_type: Mapped[str] = mapped_column(
        String(32),
        server_default="ugc",
        nullable=False,
    )
    access_mode: Mapped[str] = mapped_column(
        String(32),
        server_default="internal_stream",
        nullable=False,
    )
    source_platform: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    external_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    imported_from: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    video_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    video_processing_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    video_thumbnail_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    sc_url: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    sc_uri: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    source_url: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    canonical_source_url: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    source_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
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
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
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
    info: Mapped[TrackInfo | None] = relationship(
        back_populates="track",
        uselist=False,
        cascade="all, delete-orphan",
    )
