from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.user import User


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"
    __table_args__ = (
        Index(
            "uq_complaints_reported_by_user_track",
            "reported_by_user_id",
            "track_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reported_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    reason_type: Mapped[str] = mapped_column(
        String(30),
        server_default="other",
        nullable=False,
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    rightsholder_name: Mapped[str | None] = (
        mapped_column(String(255), nullable=True)
    )
    proof_url: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )

    track: Mapped["Track"] = relationship(
        back_populates="complaints"
    )
    reporter: Mapped["User"] = relationship()
