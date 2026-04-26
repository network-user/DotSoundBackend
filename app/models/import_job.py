from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ImportJob(Base, TimestampMixin):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="scanning",
    )
    total_tracks: Mapped[int] = mapped_column(
        Integer, default=0
    )
    completed_tracks: Mapped[int] = mapped_column(
        Integer, default=0
    )
    failed_tracks: Mapped[int] = mapped_column(
        Integer, default=0
    )
    tracks_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
