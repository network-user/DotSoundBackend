from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserEmbedding(Base):
    """Learned dense vector representing a user's taste.

    Produced periodically by a two-tower-style trainer in
    ``DotSoundComputeWorker``. The model identity is opaque to
    backend; only the vector and ``model_version`` are persisted so
    consumers can detect stale data after a model swap.
    """

    __tablename__ = "user_embeddings"
    __table_args__ = (
        Index(
            "ix_user_embeddings_model_version",
            "model_version",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    dim: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    model_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="v0",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
    )
