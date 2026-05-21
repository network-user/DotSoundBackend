from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ListenEventDaily(Base):
    __tablename__ = "listen_events_daily"
    __table_args__ = (
        PrimaryKeyConstraint(
            "day",
            "user_id",
            "track_id",
            name="pk_listen_events_daily",
        ),
        Index(
            "ix_listen_events_daily_track_day",
            "track_id",
            "day",
        ),
        Index(
            "ix_listen_events_daily_user_day",
            "user_id",
            "day",
        ),
    )

    day: Mapped[date] = mapped_column(Date, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    track_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    plays: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    listen_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    completes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    skips: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
