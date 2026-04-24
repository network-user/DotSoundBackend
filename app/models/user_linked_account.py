from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserLinkedAccount(Base, TimestampMixin):
    __tablename__ = "user_linked_accounts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider",
            name="uq_linked_account_user_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    provider_user_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    provider_username: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    access_token_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    refresh_token_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scopes: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
