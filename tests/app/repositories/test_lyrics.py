import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.lyrics import LyricsRepository
from app.repositories.track import TrackRepository

pytestmark = pytest.mark.anyio


async def _make_track(session: AsyncSession):
    user_repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    user = await user_repo.create(
        telegram_id=1,
        first_name="U",
        auth_provider="telegram",
    )
    track_repo = TrackRepository(session)
    return await track_repo.create(
        title="T",
        artist="A",
        uploaded_by_id=user.id,
    )


async def test_create_or_update_new(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    repo = LyricsRepository(session)

    lyrics = await repo.create_or_update(
        track.id, "Hello world"
    )
    assert lyrics.plain_text == "Hello world"


async def test_create_or_update_existing(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    repo = LyricsRepository(session)
    await repo.create_or_update(
        track.id, "Version 1"
    )

    updated = await repo.create_or_update(
        track.id, "Version 2"
    )
    assert updated.plain_text == "Version 2"


async def test_get_by_track_id(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    repo = LyricsRepository(session)

    assert (
        await repo.get_by_track_id(track.id) is None
    )

    await repo.create_or_update(
        track.id, "Lyrics"
    )
    found = await repo.get_by_track_id(track.id)
    assert found is not None
    assert found.plain_text == "Lyrics"


async def test_delete_by_track_id(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    repo = LyricsRepository(session)
    await repo.create_or_update(
        track.id, "Lyrics"
    )

    removed = await repo.delete_by_track_id(
        track.id
    )
    assert removed is True

    removed_again = await repo.delete_by_track_id(
        track.id
    )
    assert removed_again is False
