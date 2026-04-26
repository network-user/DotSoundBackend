from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.user import User
    from app.models.video_blob import VideoBlob


class ImageBlob(Base, TimestampMixin):
    """Content-addressed image file (SHA-256) in object storage with ref count."""

    __tablename__ = "image_blobs"

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

    cover_tracks: Mapped[list[Track]] = relationship(
        "Track",
        foreign_keys="Track.cover_blob_id",
        back_populates="cover_blob",
    )
    avatar_users: Mapped[list[User]] = relationship(
        "User",
        foreign_keys="User.avatar_blob_id",
        back_populates="avatar_blob",
    )
    video_thumbnails: Mapped[list[VideoBlob]] = relationship(
        "VideoBlob",
        foreign_keys="VideoBlob.thumbnail_blob_id",
        back_populates="thumbnail_blob",
    )
