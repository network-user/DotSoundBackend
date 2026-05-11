from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.album import Album
    from app.models.artist_catalog import ArtistCatalogReleaseTrack
    from app.models.audio_blob import AudioBlob
    from app.models.complaint import Complaint
    from app.models.image_blob import ImageBlob
    from app.models.lyrics import TrackLyrics
    from app.models.track_info import TrackInfo
    from app.models.video_blob import VideoBlob


class Track(Base, TimestampMixin):
    __tablename__ = "tracks"
    __table_args__ = (
        Index(
            "uq_tracks_sc_url",
            "sc_url",
            unique=True,
            postgresql_where=text("sc_url IS NOT NULL"),
            sqlite_where=text("sc_url IS NOT NULL"),
        ),
        Index(
            "uq_tracks_imported_from_external_id",
            "imported_from",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
            sqlite_where=text("external_id IS NOT NULL"),
        ),
        Index(
            "uq_tracks_user_blob_active",
            "uploaded_by_id",
            "blob_id",
            unique=True,
            postgresql_where=text("blob_id IS NOT NULL AND is_active IS TRUE"),
            sqlite_where=text("blob_id IS NOT NULL AND is_active = 1"),
        ),
        Index(
            "ix_tracks_user_audio_hash",
            "uploaded_by_id",
            "audio_hash",
            postgresql_where=text("audio_hash IS NOT NULL"),
            sqlite_where=text("audio_hash IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
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
    file_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    play_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    cover_key: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_from: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    video_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_processing_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    video_thumbnail_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    sc_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sc_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_source_url: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    source_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hls_manifest_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
    album_id: Mapped[int | None] = mapped_column(
        ForeignKey("albums.id", ondelete="SET NULL"),
        nullable=True,
    )
    album_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    comments_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("audio_blobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    blob_ref_freed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    cover_blob_ref_freed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    video_blob_ref_freed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    waveform_data: Mapped[list[float] | None] = mapped_column(
        JSON, nullable=True
    )
    previous_source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True
    )
    cover_blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("image_blobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    video_blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("video_blobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    composition_group_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    audio_cache_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    playback_last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    playback_last_http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    playback_last_failure_source: Mapped[str | None] = mapped_column(
        String(48),
        nullable=True,
    )
    playback_recovery_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    playback_suppressed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    lyrics_catalog_miss_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        type_=BigInteger,
        nullable=True,
    )
    deleted_reason: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    audio_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    audio_blob: Mapped[AudioBlob | None] = relationship(
        "AudioBlob",
        back_populates="tracks",
        foreign_keys=[blob_id],
    )
    cover_blob: Mapped[ImageBlob | None] = relationship(
        "ImageBlob",
        foreign_keys=[cover_blob_id],
        back_populates="cover_tracks",
    )
    video_blob: Mapped[VideoBlob | None] = relationship(
        "VideoBlob",
        foreign_keys=[video_blob_id],
        back_populates="tracks",
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
    catalog_release_links: Mapped[list[ArtistCatalogReleaseTrack]] = (
        relationship(
            back_populates="track",
            cascade="all, delete-orphan",
        )
    )
