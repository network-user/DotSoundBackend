from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from PIL import Image
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
    user, _ = await repo.upsert(telegram_id, "u", "Test", None)
    return user.id


async def _make_track(
    session: AsyncSession,
    owner_id: int | None = None,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title="T",
        file_key="k",
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

    updated = await svc.update(pl.id, uid, name="New", is_public=None)

    assert updated.name == "New"


async def test_update_playlist_not_owner(
    session: AsyncSession,
) -> None:
    uid1 = await _make_user(session, 601)
    uid2 = await _make_user(session, 602)
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid1)

    with pytest.raises(HTTPException) as exc:
        await svc.update(pl.id, uid2, name="X", is_public=None)

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


async def test_add_track_not_playable_returns_400(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    repo = TrackRepository(session)
    bad = await repo.create(
        title="NoAudio",
        file_key=None,
        access_mode="internal_stream",
        uploaded_by_id=uid,
    )
    svc = PlaylistService(session)
    pl = await svc.create("PL", uid)

    with pytest.raises(HTTPException) as exc:
        await svc.add_track(pl.id, bad.id, uid)

    assert exc.value.status_code == 400


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


async def test_auto_collage_generates_once_at_threshold(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("Mix", uid)
    repo = TrackRepository(session)

    buf = BytesIO()
    Image.new("RGB", (8, 8), (90, 120, 140)).save(
        buf,
        format="JPEG",
    )
    jpeg = buf.getvalue()

    tids: list[int] = []
    for i in range(6):
        tr = await repo.create(
            title=f"T{i}",
            file_key=f"k{i}",
            uploaded_by_id=uid,
            cover_key="covers/demo.jpg",
        )
        tids.append(tr.id)

    with (
        patch(
            "app.services.playlist_service.s3.download_object",
            new_callable=AsyncMock,
            return_value=jpeg,
        ),
        patch(
            "app.services.playlist_service.s3.upload_object",
            new_callable=AsyncMock,
        ) as upl,
    ):
        for tid in tids[:3]:
            await svc.add_track(pl.id, tid, uid)
        assert upl.await_count == 0
        await svc.add_track(pl.id, tids[3], uid)
        assert upl.await_count == 1
        refreshed = await svc.get(pl.id)
        assert refreshed is not None
        ck = refreshed.cover_key or ""
        assert ck.startswith("playlist-covers/")
        assert refreshed.collage_generated_at is not None
        await svc.add_track(pl.id, tids[4], uid)
        assert upl.await_count == 1


async def test_auto_collage_respects_opt_out(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("Mix", uid)
    pl.cover_auto_suppressed = True
    await session.flush()

    repo = TrackRepository(session)
    tids: list[int] = []
    for i in range(5):
        tr = await repo.create(
            title=f"T{i}",
            file_key=f"k{i}",
            uploaded_by_id=uid,
        )
        tids.append(tr.id)

    with patch(
        "app.services.playlist_service.s3.upload_object",
        new_callable=AsyncMock,
    ) as upl:
        for tid in tids:
            await svc.add_track(pl.id, tid, uid)

    upl.assert_not_awaited()


async def test_delete_owner_cover_sets_suppress(
    session: AsyncSession,
) -> None:
    uid = await _make_user(session)
    svc = PlaylistService(session)
    pl = await svc.create("Mix", uid)
    pl.cover_key = "playlist-covers/1/99.webp"
    await session.flush()

    with patch(
        "app.services.playlist_service.s3.delete_object",
        new_callable=AsyncMock,
    ):
        updated = await svc.delete_owner_cover(pl.id, uid)

    assert updated.cover_key is None
    assert updated.cover_auto_suppressed is True
