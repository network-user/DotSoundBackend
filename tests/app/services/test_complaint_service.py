import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.complaint_service import (
    ComplaintService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 800,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, "u", "Test", None
    )
    return user.id


async def _make_track(
    session: AsyncSession,
    owner_id: int | None = None,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="T", file_key="k",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_submit_complaint(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = ComplaintService(session)
    complaint, hidden = await svc.submit(
        track_id=tid,
        user_id=uid,
        reason="spam",
        contact_email=None,
        threshold=10,
    )

    assert complaint.reason == "spam"
    assert hidden is False


async def test_submit_duplicate_raises(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = ComplaintService(session)
    await svc.submit(
        tid, uid, "spam", None, threshold=10
    )

    with pytest.raises(ValueError, match="already"):
        await svc.submit(
            tid, uid, "again", None, threshold=10
        )


async def test_submit_auto_hides_track(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 801)
    uid2 = await _make_user(session, 802)
    uid3 = await _make_user(session, 803)
    tid = await _make_track(session, uid1)

    svc = ComplaintService(session)
    await svc.submit(
        tid, uid1, "r1", None, threshold=3
    )
    await svc.submit(
        tid, uid2, "r2", None, threshold=3
    )
    _, hidden = await svc.submit(
        tid, uid3, "r3", None, threshold=3
    )

    assert hidden is True


async def test_submit_user_not_found(
    session: AsyncSession,
) -> None:
    svc = ComplaintService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.submit(
            track_id=1,
            user_id=9999,
            reason="x",
            contact_email=None,
            threshold=5,
        )

    assert exc.value.status_code == 404
