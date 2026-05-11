from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.track import Track


class AudioBlob(Base, TimestampMixin):
    """Content-addressed audio file (SHA-256) in object storage with ref count."""

    __tablename__ = "audio_blobs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )
    content_sha256: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    source_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    hls_manifest_key: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    content_type: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ref_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )

    tracks: Mapped[list[Track]] = relationship(
        "Track",
        back_populates="audio_blob",
    )
