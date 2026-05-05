import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GenreMixOverride(Base, TimestampMixin):
    __tablename__ = "genre_mix_overrides"

    id: Mapped[int] = mapped_column(
        sa.BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    genre: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        sa.String(256),
        nullable=False,
    )
    track_ids: Mapped[list[int]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
