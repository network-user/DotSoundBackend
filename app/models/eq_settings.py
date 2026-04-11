from sqlalchemy import (
    BigInteger,
    ForeignKey,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserEqSettings(Base, TimestampMixin):
    __tablename__ = "user_eq_settings"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        unique=True,
        nullable=False,
    )
    preset: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    bands: Mapped[list] = mapped_column(
        JSON, nullable=False
    )
