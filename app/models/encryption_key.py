from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EncryptionKey(Base):
    __tablename__ = "encryption_keys"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id", ondelete="CASCADE"
        ),
        type_=BigInteger,
        unique=True,
        nullable=False,
    )
    encrypted_key: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False
    )
    key_version: Mapped[int] = mapped_column(
        Integer, server_default="1", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
