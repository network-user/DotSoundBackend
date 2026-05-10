from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
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
    from app.models.track import Track


class TrackEmbedding(Base):
    """Learned dense vector representation of a track for ANN search.

    The actual embedding model is opaque to backend (lives in
    PrivateCore / ComputeWorker). Backend only stores the resulting
    vector and the opaque ``model_version`` so consumers can detect
    stale embeddings after a model upgrade.
    """

    __tablename__ = "track_embeddings"
    __table_args__ = (
        Index(
            "ix_track_embeddings_model_version",
            "model_version",
        ),
    )

    track_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
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

    track: Mapped[Track] = relationship(
        "Track",
        foreign_keys=[track_id],
    )
