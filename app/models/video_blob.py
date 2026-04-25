from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.image_blob import ImageBlob
    from app.models.track import Track


class VideoBlob(Base, TimestampMixin):
    """Content-addressed video file (SHA-256) in object storage with ref count."""

    __tablename__ = "video_blobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_sha256: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ref_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    thumbnail_blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("image_blobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    thumbnail_blob: Mapped[ImageBlob | None] = relationship(
        "ImageBlob",
        foreign_keys=[thumbnail_blob_id],
        back_populates="video_thumbnails",
    )
    tracks: Mapped[list[Track]] = relationship(
        "Track",
        foreign_keys="Track.video_blob_id",
        back_populates="video_blob",
    )
