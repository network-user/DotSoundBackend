from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ArtistMonthlyStats(Base):
    __tablename__ = "artist_monthly_stats"
    __table_args__ = (
        UniqueConstraint(
            "artist_id",
            "year",
            "month",
            name="uq_artist_monthly_stats",
        ),
        Index(
            "ix_artist_monthly_stats_artist_id",
            "artist_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(
        SmallInteger, nullable=False
    )
    month: Mapped[int] = mapped_column(
        SmallInteger, nullable=False
    )
    unique_listeners: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    snapshotted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
