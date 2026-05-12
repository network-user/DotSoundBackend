from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.image_blob import ImageBlob


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "telegram_id IS NOT NULL OR email IS NOT NULL",
            name="ck_users_has_identity",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    username: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    first_name: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    last_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    display_name_normalized: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    avatar_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    avatar_seed: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )

    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    auth_provider: Mapped[str] = mapped_column(
        String(20), server_default="telegram", nullable=False
    )
    totp_secret_encrypted: Mapped[str | None] = (
        mapped_column(Text, nullable=True)
    )
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    backup_codes_hash: Mapped[str | None] = (
        mapped_column(Text, nullable=True)
    )
    admin_init: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    admin_totp_secret_encrypted: Mapped[str | None] = (
        mapped_column(Text, nullable=True)
    )
    admin_totp_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    admin_backup_codes_hash: Mapped[str | None] = (
        mapped_column(Text, nullable=True)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locale: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    profile_visibility: Mapped[str] = mapped_column(
        String(20),
        server_default="public",
        nullable=False,
    )
    avatar_blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("image_blobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    avatar_blob_ref_freed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )

    avatar_blob: Mapped[ImageBlob | None] = relationship(
        "ImageBlob",
        foreign_keys=[avatar_blob_id],
        back_populates="avatar_users",
    )
