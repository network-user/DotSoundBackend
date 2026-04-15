import structlog
from dotsound_private_core.services.moderation import (
    should_auto_hide_track,
)
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.repositories.complaint import ComplaintRepository
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ComplaintService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ComplaintRepository(session)
        self._user_repo = UserRepository(session)

    async def submit(
        self,
        track_id: int,
        user_id: int,
        reason: str,
        reason_type: str,
        contact_email: str | None,
        rightsholder_name: str | None,
        proof_url: str | None,
        threshold: int,
    ) -> tuple[Complaint, bool]:
        user = await self._resolve_user(user_id)

        if await self._repo.exists(user.id, track_id):
            raise ValueError("already_reported")

        complaint = await self._repo.create(
            track_id=track_id,
            user_id=user.id,
            reason=reason,
            reason_type=reason_type,
            contact_email=contact_email,
            rightsholder_name=rightsholder_name,
            proof_url=proof_url,
        )

        count = await self._repo.count_by_track(track_id)
        track_hidden = False

        if should_auto_hide_track(count, threshold):
            track = await self._session.get(Track, track_id)
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
            user_id=user.id,
            reason_type=reason_type,
            track_hidden=track_hidden,
        )
        return complaint, track_hidden

    async def _resolve_user(self, user_id: int) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(
                user_id
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
