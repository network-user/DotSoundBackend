import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.complaint import (
    ComplaintRepository,
)
from app.repositories.track import TrackRepository

pytestmark = pytest.mark.anyio


async def _seed(session: AsyncSession):
    user_repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    user = await user_repo.create(
        telegram_id=1,
        first_name="U",
        auth_provider="telegram",
    )
    track_repo = TrackRepository(session)
    track = await track_repo.create(
        title="T",
        artist="A",
        uploaded_by_id=user.id,
    )
    return user, track


async def test_create_complaint(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = ComplaintRepository(session)

    complaint = await repo.create(
        track_id=track.id,
        user_id=user.id,
        reason="spam",
        reason_type="copyright",
        contact_email=None,
        rightsholder_name="Rights Holder",
        proof_url="https://example.com/proof",
    )

    assert complaint.id is not None
    assert complaint.reason == "spam"
    assert complaint.reason_type == "copyright"
    assert complaint.rightsholder_name == "Rights Holder"


async def test_count_by_track(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = ComplaintRepository(session)

    assert await repo.count_by_track(track.id) == 0

    await repo.create(
        track_id=track.id,
        user_id=user.id,
        reason="spam",
        reason_type="other",
        contact_email=None,
        rightsholder_name=None,
        proof_url=None,
    )
    assert await repo.count_by_track(track.id) == 1


async def test_exists(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = ComplaintRepository(session)

    assert (
        await repo.exists(user.id, track.id)
        is False
    )

    await repo.create(
        track_id=track.id,
        user_id=user.id,
        reason="copyright",
        reason_type="copyright",
        contact_email="a@b.com",
        rightsholder_name="Holder",
        proof_url="https://example.com/proof",
    )
    assert (
        await repo.exists(user.id, track.id) is True
    )
