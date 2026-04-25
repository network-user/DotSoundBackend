import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.track import TrackRepository

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1,
) -> User:
    repo: BaseRepository[User] = BaseRepository(
        session, User
    )
    return await repo.create(
        telegram_id=telegram_id,
        first_name="U",
        auth_provider="telegram",
    )


async def test_create_track(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)

    track = await repo.create(
        title="Song A",
        artist="Artist A",
        uploaded_by_id=user.id,
    )

    assert track.id is not None
    assert track.title == "Song A"


async def test_list_active_pagination(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)
    for i in range(5):
        await repo.create(
            title=f"T{i}",
            artist="A",
            uploaded_by_id=user.id,
        )

    tracks, total = await repo.list_active(
        offset=0, limit=3
    )
    assert total == 5
    assert len(tracks) == 3

    tracks2, _ = await repo.list_active(
        offset=3, limit=3
    )
    assert len(tracks2) == 2


async def test_search(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)
    await repo.create(
        title="Needle",
        artist="Haystack",
        uploaded_by_id=user.id,
    )
    await repo.create(
        title="Other",
        artist="Other",
        uploaded_by_id=user.id,
    )

    tracks, total = await repo.search("Needle")
    assert total == 1
    assert tracks[0].title == "Needle"


async def test_increment_play_count(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Play",
        artist="A",
        uploaded_by_id=user.id,
    )
    assert track.play_count == 0

    ok = await repo.increment_play_count(track.id)
    assert ok is True

    await session.refresh(track)
    assert track.play_count == 1

    missing = await repo.increment_play_count(9999)
    assert missing is False


async def test_update_track(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Old",
        artist="Old Artist",
        uploaded_by_id=user.id,
    )

    updated = await repo.update_track(
        track.id,
        user.id,
        title="New",
        artist="New Artist",
        genre="Rock",
        description="A description",
    )
    assert updated is not None
    assert updated.title == "New"
    assert updated.artist == "New Artist"
    assert updated.genre == "Rock"
    assert updated.description == "A description"


async def test_update_track_wrong_owner(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    other = await _make_user(session, telegram_id=99)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Mine",
        artist="A",
        uploaded_by_id=user.id,
    )

    result = await repo.update_track(
        track.id, other.id, title="Stolen"
    )
    assert result is None


async def test_update_track_no_fields(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)
    track = await repo.create(
        title="NoChange",
        artist="A",
        uploaded_by_id=user.id,
    )

    result = await repo.update_track(track.id, user.id)
    assert result is None


async def test_delete_by_owner(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    other = await _make_user(session, telegram_id=2)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Del",
        artist="A",
        uploaded_by_id=user.id,
    )

    result = await repo.delete_by_owner(
        track.id, other.id
    )
    assert result is None

    result = await repo.delete_by_owner(
        track.id, user.id
    )
    assert result is not None
    assert result.is_active is False


async def test_find_by_title_and_duration_exact(
    session: AsyncSession,
) -> None:
    from app.models.track import Track

    user = await _make_user(session, telegram_id=300)
    t = Track(
        title="Perfect Match",
        artist="A",
        duration_seconds=200,
        source_platform="youtube",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    session.add(t)
    await session.flush()

    repo = TrackRepository(session)
    results = await repo.find_by_title_and_duration(
        title="Perfect Match",
        duration_seconds=200,
        platform="youtube",
    )
    assert len(results) == 1
    assert results[0].id == t.id


async def test_find_by_title_and_duration_within_tolerance(
    session: AsyncSession,
) -> None:
    from app.models.track import Track

    user = await _make_user(session, telegram_id=301)
    t = Track(
        title="Tolerance Track",
        artist="A",
        duration_seconds=210,
        source_platform="soundcloud",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    session.add(t)
    await session.flush()

    repo = TrackRepository(session)
    results = await repo.find_by_title_and_duration(
        title="Tolerance Track",
        duration_seconds=200,
        platform="soundcloud",
    )
    assert len(results) == 1


async def test_find_by_title_and_duration_outside_tolerance(
    session: AsyncSession,
) -> None:
    from app.models.track import Track

    user = await _make_user(session, telegram_id=302)
    t = Track(
        title="Far Away",
        artist="A",
        duration_seconds=400,
        source_platform="bandcamp",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    session.add(t)
    await session.flush()

    repo = TrackRepository(session)
    results = await repo.find_by_title_and_duration(
        title="Far Away",
        duration_seconds=200,
        platform="bandcamp",
    )
    assert results == []


async def test_find_by_title_and_duration_wrong_platform(
    session: AsyncSession,
) -> None:
    from app.models.track import Track

    user = await _make_user(session, telegram_id=303)
    t = Track(
        title="Platform Check",
        artist="A",
        duration_seconds=180,
        source_platform="youtube",
        is_active=True,
        is_public=True,
        uploaded_by_id=user.id,
    )
    session.add(t)
    await session.flush()

    repo = TrackRepository(session)
    results = await repo.find_by_title_and_duration(
        title="Platform Check",
        duration_seconds=180,
        platform="soundcloud",
    )
    assert results == []
