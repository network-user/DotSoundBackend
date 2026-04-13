import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.track_service import TrackService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 500,
) -> int:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id, "u", "Test", None
    )
    return user.id


async def _make_track(
    session: AsyncSession,
    owner_id: int | None = None,
    title: str = "T",
    file_key: str = "k",
    genre: str | None = None,
    is_public: bool = True,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title=title,
        file_key=file_key,
        uploaded_by_id=owner_id,
        genre=genre,
        is_public=is_public,
    )
    return track.id


async def test_list_tracks_empty(
    session: AsyncSession,
) -> None:
    svc = TrackService(session)

    tracks, total = await svc.list_tracks()

    assert tracks == []
    assert total == 0


async def test_list_tracks_returns_active(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    await _make_track(session, uid)

    svc = TrackService(session)
    tracks, total = await svc.list_tracks()

    assert total == 1
    assert len(tracks) == 1


async def test_get_track_found(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)

    svc = TrackService(session)
    track = await svc.get_track(tid)

    assert track is not None
    assert track.id == tid


async def test_get_track_not_found(
    session: AsyncSession,
) -> None:
    svc = TrackService(session)

    track = await svc.get_track(9999)

    assert track is None


async def test_search_tracks(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    await _make_track(
        session, uid, title="Midnight Song"
    )

    svc = TrackService(session)
    tracks, total = await svc.search("Midnight")

    assert total == 1
    assert tracks[0].title == "Midnight Song"


async def test_search_no_results(
    session: AsyncSession,
) -> None:
    svc = TrackService(session)

    tracks, total = await svc.search("nonexistent")

    assert total == 0
    assert tracks == []


async def test_list_by_user(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    await _make_track(session, uid)

    svc = TrackService(session)
    tracks, total = await svc.list_by_user(uid)

    assert total == 1


async def test_get_genres(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    await _make_track(
        session, uid, genre="electronic"
    )
    await _make_track(
        session, uid, genre="rock"
    )

    svc = TrackService(session)
    genres = await svc.get_genres()

    assert "electronic" in genres
    assert "rock" in genres


async def test_list_public_by_user(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    await _make_track(session, uid, is_public=True)
    await _make_track(session, uid, is_public=False)

    svc = TrackService(session)
    tracks, total = await svc.list_public_by_user(
        uid
    )

    assert total == 1


async def test_list_public_by_user_not_found(
    session: AsyncSession,
) -> None:
    svc = TrackService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.list_public_by_user(9999)

    assert exc.value.status_code == 404
