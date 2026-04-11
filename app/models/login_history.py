from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LoginHistory(Base, TimestampMixin):
    __tablename__ = "login_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        nullable=False,
        index=True,
    )
    ip: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    device: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    login_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
