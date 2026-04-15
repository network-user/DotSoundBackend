from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"

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

    track: Mapped["Track"] = relationship(  # type: ignore[name-defined]
        back_populates="complaints"
    )
    reporter: Mapped["User"] = relationship()  # type: ignore[name-defined]
