from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.artist import Artist
    from app.models.track import Track


class ArtistCatalogRelease(Base, TimestampMixin):
    __tablename__ = "artist_catalog_releases"
    __table_args__ = (
        Index(
            "uq_artist_catalog_releases_artist_sc_album",
            "artist_id",
            "soundcloud_album_id",
            unique=True,
            postgresql_where=text("soundcloud_album_id IS NOT NULL"),
            sqlite_where=text("soundcloud_album_id IS NOT NULL"),
        ),
        Index(
            "ix_artist_catalog_releases_artist_id",
            "artist_id",
        ),
        Index(
            "ix_artist_catalog_releases_artist_display_pos",
            "artist_id",
            "display_position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    release_kind: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    cover_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    soundcloud_album_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    display_position: Mapped[int] = mapped_column(
        Integer,
        server_default="0",
        nullable=False,
    )
    manual_lock: Mapped[bool] = mapped_column(
        Boolean,
        server_default=false(),
        nullable=False,
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    artist: Mapped[Artist] = relationship(
        back_populates="catalog_releases",
    )
    track_links: Mapped[list[ArtistCatalogReleaseTrack]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class ArtistCatalogReleaseTrack(Base):
    __tablename__ = "artist_catalog_release_tracks"
    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "track_id",
            name="uq_catalog_release_track",
        ),
        UniqueConstraint(
            "release_id",
            "position",
            name="uq_catalog_release_position",
        ),
        Index(
            "ix_artist_catalog_release_tracks_release_id",
            "release_id",
        ),
        Index(
            "ix_artist_catalog_release_tracks_track_id",
            "track_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(
        ForeignKey(
            "artist_catalog_releases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    release: Mapped[ArtistCatalogRelease] = relationship(
        back_populates="track_links",
    )
    track: Mapped[Track] = relationship(
        back_populates="catalog_release_links",
    )
