from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TrackLyrics(Base, TimestampMixin):
    __tablename__ = "track_lyrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plain_text: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    synced_lines: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="manual"
    )
    source_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    sync_quality: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    sync_profile: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )

    track = relationship("Track", back_populates="lyrics")
