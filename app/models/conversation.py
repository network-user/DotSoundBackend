from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    title: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (
        Index(
            "ix_conversation_members_user_id",
            "user_id",
        ),
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id", ondelete="CASCADE"
        ),
        type_=BigInteger,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(
        String(10),
        server_default="member",
        nullable=False,
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    is_muted: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    last_read_message_id: Mapped[int | None] = (
        mapped_column(
            BigInteger, nullable=True
        )
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
