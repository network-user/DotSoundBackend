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

from app.models.base import Base


class ListenEvent(Base):
    __tablename__ = "listen_events"
    __table_args__ = (
        Index(
            "ix_listen_events_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_listen_events_track_created",
            "track_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_listened_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    total_duration_seconds: Mapped[int | None] = (
        mapped_column(Integer, nullable=True)
    )
    completed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    skipped: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    source_context: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
