from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, String
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
    onboarding_import_acknowledged: Mapped[bool] = (
        mapped_column(
            Boolean, server_default="false", nullable=False
        )
    )
    auth_first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_play_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    legal_accepted_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    legal_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_adult_confirmed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    adult_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
