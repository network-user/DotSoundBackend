from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.track import Track
from app.models.user import User
from app.services.admin_service import AdminService

pytestmark = pytest.mark.anyio


async def _seed_user(
    db_session: AsyncSession,
    *,
    telegram_id: int,
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name=f"User-{telegram_id}",
        is_admin=is_admin,
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_track(
    db_session: AsyncSession,
    *,
    title: str,
    uploader_id: int,
    is_active: bool = True,
    source: str = "internal",
) -> Track:
    track = Track(
        title=title,
        artist="Artist",
        uploaded_by_id=uploader_id,
        is_active=is_active,
        is_public=True,
        source=source,
    )
    db_session.add(track)
    await db_session.flush()
    return track


async def test_admin_service_list_tracks_filters(
    db_session: AsyncSession,
) -> None:
    uploader = await _seed_user(
        db_session, telegram_id=400001
    )
    await _seed_track(
        db_session,
        title="visible",
        uploader_id=uploader.id,
        is_active=True,
    )
    await _seed_track(
        db_session,
        title="hidden",
        uploader_id=uploader.id,
        is_active=False,
    )
    service = AdminService(db_session)
    rows, total = await service.list_tracks(
        page=1, size=10, is_active=True
    )
    assert total == 1
    assert rows[0].title == "visible"
    rows, total = await service.list_tracks(
        page=1,
        size=10,
        search="hid",
    )
    assert total == 1
    assert rows[0].title == "hidden"


async def test_admin_service_list_users_search(
    db_session: AsyncSession,
) -> None:
    await _seed_user(
        db_session, telegram_id=400010
    )
    await _seed_user(
        db_session,
        telegram_id=400011,
        is_admin=True,
    )
    service = AdminService(db_session)
    rows, total = await service.list_users(
        page=1, size=20, is_admin=True
    )
    assert total == 1
    assert rows[0].is_admin is True


async def test_admin_service_set_visibility(
    db_session: AsyncSession,
) -> None:
    uploader = await _seed_user(
        db_session, telegram_id=400020
    )
    track = await _seed_track(
        db_session,
        title="t",
        uploader_id=uploader.id,
    )
    service = AdminService(db_session)
    out = await service.set_track_visibility(
        track.id, False
    )
    assert out is not None
    assert out.is_active is False


async def test_admin_service_delete_track_calls_s3(
    db_session: AsyncSession,
) -> None:
    uploader = await _seed_user(
        db_session, telegram_id=400030
    )
    track = await _seed_track(
        db_session,
        title="t",
        uploader_id=uploader.id,
    )
    track.file_key = "uploads/x.mp3"
    track.cover_key = "covers/x.jpg"
    await db_session.flush()
    service = AdminService(db_session)
    with patch(
        "app.services.admin_service.s3.delete_object",
        new_callable=AsyncMock,
    ) as delete_mock:
        ok = await service.delete_track(track.id)
    assert ok is True
    paths = sorted(
        call.args[0] for call in delete_mock.call_args_list
    )
    assert paths == [
        "covers/x.jpg",
        "uploads/x.mp3",
    ]


async def test_admin_service_resolve_complaint(
    db_session: AsyncSession,
) -> None:
    uploader = await _seed_user(
        db_session, telegram_id=400040
    )
    track = await _seed_track(
        db_session,
        title="t",
        uploader_id=uploader.id,
    )
    complaint = Complaint(
        track_id=track.id,
        reported_by_user_id=uploader.id,
        reason="bad",
        reason_type="user",
        is_resolved=False,
    )
    db_session.add(complaint)
    await db_session.flush()
    service = AdminService(db_session)
    resolved = (
        await service.resolve_complaint(
            complaint.id
        )
    )
    assert resolved is not None
    assert resolved.is_resolved is True


async def test_admin_service_get_popular_genres(
    db_session: AsyncSession,
) -> None:
    uploader = await _seed_user(
        db_session, telegram_id=400050
    )
    for genre, count in [
        ("rock", 3),
        ("pop", 2),
        ("jazz", 1),
    ]:
        for n in range(count):
            track = await _seed_track(
                db_session,
                title=f"{genre}-{n}",
                uploader_id=uploader.id,
            )
            track.genre = genre
            await db_session.flush()
    service = AdminService(db_session)
    rows = await service.get_popular_genres(
        limit=10
    )
    assert rows[0]["genre"] == "rock"
    assert rows[0]["count"] == 3
