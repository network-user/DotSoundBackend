from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Experiment(Base, TimestampMixin):
    """Recsys experiment with weighted arms.

    ``arms`` is a JSON map of arm_name -> integer share. Backend
    uses ``dotsound_private_core.services.ab_policy.assign_arm`` to
    pick a deterministic arm per (user, experiment_key).
    """

    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_status", "status"),)

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    arms: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="draft",
    )
    is_holdout: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )


class ExperimentAssignment(Base):
    """Materialized record of an arm assignment.

    Caching the assignment ensures replays land on the same arm
    even after the experiment configuration changes.
    """

    __tablename__ = "experiment_assignments"
    __table_args__ = (
        Index(
            "ix_experiment_assignments_user",
            "user_id",
            "experiment_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    experiment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    arm: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
