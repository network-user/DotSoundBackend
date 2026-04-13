import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.playlist import PlaylistRepository
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


async def test_create_and_list(
    session: AsyncSession,
) -> None:
    user, _ = await _seed(session)
    repo = PlaylistRepository(session)

    pl = await repo.create(
        name="My List",
        owner_id=user.id,
        is_public=True,
    )
    assert pl.id is not None
    assert pl.name == "My List"

    playlists, total = await repo.list_by_owner(
        user.id
    )
    assert total == 1
    assert playlists[0].id == pl.id


async def test_add_track_and_get_tracks(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = PlaylistRepository(session)
    pl = await repo.create(
        name="PL",
        owner_id=user.id,
        is_public=True,
    )

    pt = await repo.add_track(pl.id, track.id)
    assert pt.playlist_id == pl.id

    tracks = await repo.get_tracks(pl.id)
    assert len(tracks) == 1
    assert tracks[0].id == track.id


async def test_remove_track(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = PlaylistRepository(session)
    pl = await repo.create(
        name="PL",
        owner_id=user.id,
        is_public=True,
    )
    await repo.add_track(pl.id, track.id)

    removed = await repo.remove_track(
        pl.id, track.id
    )
    assert removed is True

    tracks = await repo.get_tracks(pl.id)
    assert tracks == []


async def test_add_track_idempotent(
    session: AsyncSession,
) -> None:
    user, track = await _seed(session)
    repo = PlaylistRepository(session)
    pl = await repo.create(
        name="PL",
        owner_id=user.id,
        is_public=True,
    )

    pt1 = await repo.add_track(pl.id, track.id)
    pt2 = await repo.add_track(pl.id, track.id)
    assert pt1.playlist_id == pt2.playlist_id
    assert pt1.track_id == pt2.track_id

    tracks = await repo.get_tracks(pl.id)
    assert len(tracks) == 1
