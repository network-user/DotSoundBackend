from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TrackLyricsTranslation(Base, TimestampMixin):
    __tablename__ = "track_lyrics_translations"
    __table_args__ = (
        UniqueConstraint(
            "track_lyrics_id",
            "language_code",
            name="uq_track_lyrics_translations_language",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_lyrics_id: Mapped[int] = mapped_column(
        ForeignKey("track_lyrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language_code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)

    lyrics = relationship("TrackLyrics", back_populates="translations")
