from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackComment(Base, TimestampMixin):
    __tablename__ = "track_comments"
    __table_args__ = (
        Index(
            "ix_track_comments_track_created",
            "track_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    is_hidden_by_author: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )


class CommentHide(Base):
    __tablename__ = "comment_hides"

    comment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "track_comments.id", ondelete="CASCADE"
        ),
        type_=BigInteger,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        primary_key=True,
    )


class CommentVote(Base):
    __tablename__ = "comment_votes"

    comment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "track_comments.id", ondelete="CASCADE"
        ),
        type_=BigInteger,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        primary_key=True,
    )
    is_like: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
