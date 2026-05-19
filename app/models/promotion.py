from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin

PROMOTION_ENTITY_TYPES: tuple[str, ...] = (
    "artist",
    "track",
    "playlist",
    "album",
)

PROMOTION_SURFACES: tuple[str, ...] = (
    "hero",
    "section",
    "in_feed",
    "search_pin",
)


class Promotion(Base, TimestampMixin):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('artist','track','playlist','album')",
            name="ck_promotions_entity_type",
        ),
        Index(
            "ix_promotions_active_window",
            "is_active",
            "starts_at",
            "ends_at",
        ),
        Index(
            "ix_promotions_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_promotions_priority",
            "priority",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    surfaces: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        server_default="[]",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    title_override: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )
    subtitle_override: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    cta_label_override: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    cover_url_override: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class PromotionEvent(Base):
    __tablename__ = "promotion_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('impression','click')",
            name="ck_promotion_events_event_type",
        ),
        Index(
            "ix_promotion_events_promotion",
            "promotion_id",
            "event_type",
            "occurred_at",
        ),
        Index(
            "ix_promotion_events_occurred_at",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    promotion_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("promotions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    surface: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
