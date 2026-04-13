import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.lyrics_service import (
    LyricsService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1400,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, "u", "Test", None
    )
    return user.id


async def _make_track(
    session: AsyncSession,
    owner_id: int,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="T", file_key="k",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_create_or_update_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    lyrics = await svc.create_or_update(
        tid, uid, "Line 1\nLine 2"
    )

    assert lyrics.plain_text == "Line 1\nLine 2"
    assert lyrics.track_id == tid


async def test_get_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    await svc.create_or_update(
        tid, uid, "Hello World"
    )

    result = await svc.get_lyrics(tid, uid)

    assert result is not None
    assert result.plain_text == "Hello World"


async def test_get_lyrics_track_not_found(
    session: AsyncSession,
) -> None:
    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_lyrics(9999)

    assert exc.value.status_code == 404


async def test_create_lyrics_not_owner(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 1401)
    uid2 = await _make_user(session, 1402)
    tid = await _make_track(session, uid1)

    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.create_or_update(
            tid, uid2, "text"
        )

    assert exc.value.status_code == 403


async def test_delete_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    await svc.create_or_update(
        tid, uid, "text"
    )

    removed = await svc.delete_lyrics(tid, uid)

    assert removed is True


async def test_delete_lyrics_not_existing(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    removed = await svc.delete_lyrics(tid, uid)

    assert removed is False


async def test_update_sync(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)
    await svc.create_or_update(
        tid, uid, "Line 1"
    )

    synced = [{"time": 0, "text": "Line 1"}]
    lyrics = await svc.update_sync(
        tid, uid, synced
    )

    assert lyrics.synced_lines == synced


async def test_update_sync_no_lyrics(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = LyricsService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.update_sync(
            tid, uid, [{"time": 0, "text": "X"}]
        )

    assert exc.value.status_code == 404
