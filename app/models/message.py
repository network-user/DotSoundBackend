from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_conversation_created",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id", ondelete="CASCADE"
        ),
        type_=BigInteger,
        nullable=False,
    )
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        type_=BigInteger,
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(20), server_default="text", nullable=False
    )
    encrypted_content: Mapped[bytes | None] = (
        mapped_column(LargeBinary, nullable=True)
    )
    content_nonce: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        type_=BigInteger,
        nullable=True,
    )
    shared_track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"),
        nullable=True,
    )
    shared_album_id: Mapped[int | None] = mapped_column(
        ForeignKey("albums.id", ondelete="SET NULL"),
        nullable=True,
    )
    shared_playlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("playlists.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )


class MessageReaction(Base):
    __tablename__ = "message_reactions"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        type_=BigInteger,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        primary_key=True,
    )
    reaction_type: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
        index=True,
    )
    file_key: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    file_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    waveform: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    width: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    height: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
