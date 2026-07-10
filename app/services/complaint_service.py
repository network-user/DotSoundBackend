import structlog
from dotsound_private_core.services.moderation import (
    should_auto_hide_track,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.repositories.complaint import ComplaintRepository
from app.repositories.user import UserRepository
from app.services.audio_blob_service import AudioBlobService

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

        try:
            complaint = await self._repo.create(
                track_id=track_id,
                user_id=user.id,
                reason=reason,
                reason_type=reason_type,
                contact_email=contact_email,
                rightsholder_name=rightsholder_name,
                proof_url=proof_url,
            )
        except IntegrityError:
            # An IntegrityError here can mean two very different things:
            # (a) we lost a race against a concurrent submit for the
            # same (user, track) pair -- the exists() check above and
            # this insert are not atomic, so two in-flight requests can
            # both pass the check, and the uq_complaints_reported_by_
            # user_track index (0122) catches what the precheck could
            # not; or (b) a genuinely different violation, e.g. the FK
            # to a track deleted between the precheck and the insert.
            # Only (a) is the idempotent "already_reported" outcome;
            # (b) must surface, not be masked as a duplicate. Re-run
            # the same existence probe after rollback to tell them
            # apart.
            await self._session.rollback()
            if await self._repo.exists(user.id, track_id):
                raise ValueError("already_reported") from None
            raise

        # Lock the track row to prevent concurrent complaint races
        result = await self._session.execute(
            select(Track)
            .where(Track.id == track_id)
            .with_for_update()
        )
        track = result.scalar_one_or_none()

        count = await self._repo.count_by_track(track_id)
        track_hidden = False

        if should_auto_hide_track(
            count, threshold
        ) and track and track.is_active:
            track.is_active = False
            ab = AudioBlobService(self._session)
            await ab.try_release_for_track(track)
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
