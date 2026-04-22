from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserTrackLibrary(Base):
    """Many-to-many link between users and tracks they have in
    their personal library.

    A track lands in a user's library when they upload it (UGC),
    import it from an external source (Yandex Music, Spotify, etc.),
    or pull it from their Telegram audios. The same canonical
    Track row appears in every importer's library — without this
    table the second importer would just hit dedup at the Track
    level and lose all visibility.

    Composite primary key on ``(user_id, track_id)`` enforces
    "one entry per user per track"; further imports of the same
    track by the same user are no-ops via ``ON CONFLICT DO NOTHING``.
    """

    __tablename__ = "user_track_library"
    __table_args__ = (
        Index(
            "ix_user_track_library_user_id_imported_at",
            "user_id",
            "imported_at",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        type_=BigInteger,
        primary_key=True,
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
