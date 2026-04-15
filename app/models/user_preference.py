from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserPreference(Base, TimestampMixin):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        unique=True,
        nullable=False,
    )
    preferred_genres: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )
    preferred_artist_ids: Mapped[list | None] = (
        mapped_column(JSON, nullable=True)
    )
    preferred_moods: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    calibration_completed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
