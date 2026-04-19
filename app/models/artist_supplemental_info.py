from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ArtistSupplementalInfo(Base):
    __tablename__ = "artist_supplemental_info"

    artist_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("artists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), server_default="pending", nullable=False
    )
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    artist = relationship("Artist", back_populates="supplemental_info")
