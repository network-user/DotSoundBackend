import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.album_service import AlbumService

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 700,
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


async def test_create_album(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = AlbumService(session)

    album = await svc.create(uid, "My Album")

    assert album.title == "My Album"
    assert album.owner_id == uid


async def test_get_by_id(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = AlbumService(session)
    album = await svc.create(uid, "A")

    found = await svc.get_by_id(album.id)

    assert found is not None
    assert found.id == album.id


async def test_get_by_id_not_found(
    session: AsyncSession,
) -> None:
    svc = AlbumService(session)

    found = await svc.get_by_id(9999)

    assert found is None


async def test_list_by_user(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = AlbumService(session)
    await svc.create(uid, "A1")
    await svc.create(uid, "A2")

    albums, total = await svc.list_by_user(uid)

    assert total == 2


async def test_update_album(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = AlbumService(session)
    album = await svc.create(uid, "Old")

    updated = await svc.update(
        album.id, uid, title="New"
    )

    assert updated.title == "New"


async def test_update_album_not_owner(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 701)
    uid2 = await _make_user(session, 702)
    svc = AlbumService(session)
    album = await svc.create(uid1, "A")

    with pytest.raises(HTTPException) as exc:
        await svc.update(album.id, uid2, title="X")

    assert exc.value.status_code == 403


async def test_delete_album(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = AlbumService(session)
    album = await svc.create(uid, "Del")

    await svc.delete(album.id, uid)

    assert await svc.get_by_id(album.id) is None


async def test_add_track_to_album(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = AlbumService(session)
    album = await svc.create(uid, "A")

    await svc.add_track(album.id, tid, uid)

    with_tracks = await svc.get_with_tracks(
        album.id
    )
    assert with_tracks is not None
    assert any(
        t.id == tid for t in with_tracks.tracks
    )


async def test_add_track_not_owner(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 703)
    uid2 = await _make_user(session, 704)
    tid = await _make_track(session, uid2)
    svc = AlbumService(session)
    album = await svc.create(uid1, "A")

    with pytest.raises(HTTPException) as exc:
        await svc.add_track(album.id, tid, uid1)

    assert exc.value.status_code == 403


async def test_remove_track_from_album(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    tid = await _make_track(session, uid)
    svc = AlbumService(session)
    album = await svc.create(uid, "A")
    await svc.add_track(album.id, tid, uid)

    await svc.remove_track(album.id, tid, uid)

    with_tracks = await svc.get_with_tracks(
        album.id
    )
    assert with_tracks is not None
    assert len(with_tracks.tracks) == 0


async def test_update_album_admin_override_requires_admin_actor(
    session: AsyncSession,
) -> None:
    owner_id = await _make_user(session, 705)
    actor_id = await _make_user(session, 706)
    svc = AlbumService(session)
    album = await svc.create(owner_id, "A")

    with pytest.raises(HTTPException) as exc:
        await svc.update(
            album.id,
            actor_id,
            title="Admin try",
            allow_admin=True,
        )

    assert exc.value.status_code == 403
