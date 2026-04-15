from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint


class ComplaintRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        track_id: int,
        user_id: int,
        reason: str,
        reason_type: str,
        contact_email: str | None,
        rightsholder_name: str | None,
        proof_url: str | None,
    ) -> Complaint:
        complaint = Complaint(
            track_id=track_id,
            reported_by_user_id=user_id,
            reason=reason,
            reason_type=reason_type,
            contact_email=contact_email,
            rightsholder_name=rightsholder_name,
            proof_url=proof_url,
        )
        self._db.add(complaint)
        await self._db.flush()
        await self._db.refresh(complaint)
        return complaint

    async def count_by_track(self, track_id: int) -> int:
        result = await self._db.execute(
            select(func.count()).where(
                Complaint.track_id == track_id
            )
        )
        return result.scalar_one()

    async def list_by_track(
        self, track_id: int
    ) -> list[Complaint]:
        result = await self._db.execute(
            select(Complaint)
            .where(Complaint.track_id == track_id)
            .order_by(Complaint.created_at.desc())
        )
        return list(result.scalars().all())

    async def exists(
        self, user_id: int, track_id: int
    ) -> bool:
        result = await self._db.execute(
            select(Complaint.id).where(
                Complaint.reported_by_user_id == user_id,
                Complaint.track_id == track_id,
            )
        )
        return result.scalar_one_or_none() is not None
