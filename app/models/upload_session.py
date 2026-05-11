from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UploadSession(Base, TimestampMixin):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        Index(
            "ix_upload_sessions_user_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_upload_sessions_expires_at",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    upload_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    audio_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_chunks: Mapped[list[int]] = mapped_column(
        JSON, default=list, nullable=False
    )
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    s3_multipart_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_parts: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), server_default="active", nullable=False
    )
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
