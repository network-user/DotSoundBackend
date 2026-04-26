from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackUploadMeta(Base, TimestampMixin):
    __tablename__ = "track_upload_meta"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    upload_ip: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    upload_user_agent: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    upload_terms_accepted: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    upload_terms_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    upload_telegram_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
