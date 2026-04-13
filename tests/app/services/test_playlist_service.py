import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.playlist_service import (
    PlaylistService,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 600,
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


async def test_create_playlist(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)

    pl = await svc.create("My Playlist", uid)

    assert pl.name == "My Playlist"
    assert pl.owner_id == uid


async def test_get_playlist(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid)

    found = await svc.get(pl.id)

    assert found is not None
    assert found.id == pl.id


async def test_get_playlist_not_found(
    session: AsyncSession,
) -> None:
    svc = PlaylistService(session)

    found = await svc.get(9999)

    assert found is None


async def test_list_by_owner(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    await svc.create("PL1", uid)
    await svc.create("PL2", uid)

    playlists, total = await svc.list_by_owner(uid)

    assert total == 2


async def test_update_playlist(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("Old", uid)

    updated = await svc.update(
        pl.id, uid, name="New", is_public=None
    )

    assert updated.name == "New"


async def test_update_playlist_not_owner(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 601)
    uid2 = await _make_user(session, 602)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid1)

    with pytest.raises(HTTPException) as exc:
        await svc.update(
            pl.id, uid2, name="X", is_public=None
        )

    assert exc.value.status_code == 403


async def test_delete_playlist(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("ToDelete", uid)

    await svc.delete(pl.id, uid)

    assert await svc.get(pl.id) is None


async def test_add_and_get_tracks(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid)

    await svc.add_track(pl.id, tid, uid)
    tracks = await svc.get_tracks(pl.id)

    assert len(tracks) == 1
    assert tracks[0].id == tid


async def test_add_track_not_found(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid)

    with pytest.raises(HTTPException) as exc:
        await svc.add_track(pl.id, 9999, uid)

    assert exc.value.status_code == 404


async def test_remove_track(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid)
    await svc.add_track(pl.id, tid, uid)

    await svc.remove_track(pl.id, tid, uid)
    tracks = await svc.get_tracks(pl.id)

    assert len(tracks) == 0


async def test_remove_track_not_in_playlist(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid)

    with pytest.raises(HTTPException) as exc:
        await svc.remove_track(pl.id, tid, uid)

    assert exc.value.status_code == 404
