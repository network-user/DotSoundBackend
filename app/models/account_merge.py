from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AccountMerge(Base, TimestampMixin):
    __tablename__ = "account_merges"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )
    source_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id", ondelete="SET NULL"
        ),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id", ondelete="SET NULL"
        ),
        nullable=False,
        index=True,
    )
    merged_data_summary: Mapped[str | None] = (
        mapped_column(Text, nullable=True)
    )
