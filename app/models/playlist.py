from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

PLAYLIST_TYPE_USER = "user"
PLAYLIST_TYPE_EDITORIAL = "editorial"
PLAYLIST_TYPE_IMPORTED_SC = "imported_sc"
PLAYLIST_TYPE_IMPORTED_BC = "imported_bc"
PLAYLIST_TYPE_AUTO_WEEKLY_TOP = "auto_weekly_top"
PLAYLIST_TYPE_AUTO_GENRE_MIX = "auto_genre_mix"
PLAYLIST_TYPE_AUTO_DAILY_MIX = "auto_daily_mix"


class Playlist(Base, TimestampMixin):
    __tablename__ = "playlists"
    __table_args__ = (Index("ix_playlists_is_featured", "is_featured"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
        index=True,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    playlist_type: Mapped[str] = mapped_column(
        String(50),
        server_default=PLAYLIST_TYPE_USER,
        nullable=False,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_auto_suppressed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    collage_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
