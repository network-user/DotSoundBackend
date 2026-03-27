import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.track import Track
from app.repositories.complaint import ComplaintRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ComplaintService:
    async def submit(
        self,
        db: AsyncSession,
        track_id: int,
        user_id: int,
        reason: str,
        contact_email: str | None,
        threshold: int,
    ) -> tuple[Complaint, bool]:
        repo = ComplaintRepository(db)

        if await repo.exists(user_id, track_id):
            raise ValueError("already_reported")

        complaint = await repo.create(
            track_id=track_id,
            user_id=user_id,
            reason=reason,
            contact_email=contact_email,
        )

        count = await repo.count_by_track(track_id)
        track_hidden = False

        if count >= threshold:
            track = await db.get(Track, track_id)
            if track and track.is_active:
                track.is_active = False
                track_hidden = True
                logger.warning(
                    "track_auto_hidden",
                    track_id=track_id,
                    complaint_count=count,
                    threshold=threshold,
                )

        logger.info(
            "complaint_submitted",
            complaint_id=complaint.id,
            track_id=track_id,
            user_id=user_id,
            track_hidden=track_hidden,
        )
        return complaint, track_hidden
