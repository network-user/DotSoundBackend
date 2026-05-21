import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.track import TrackRepository
from app.repositories.user_track_library import (
    UserTrackLibraryRepository,
)

pytestmark = pytest.mark.anyio


async def _make_user(session: AsyncSession, telegram_id: int) -> User:
    repo: BaseRepository[User] = BaseRepository(session, User)
    return await repo.create(
        telegram_id=telegram_id,
        first_name=f"U{telegram_id}",
        auth_provider="telegram",
    )


async def _make_track(
    session: AsyncSession, uploader_id: int, title: str = "T"
) -> Track:
    track_repo = TrackRepository(session)
    return await track_repo.create(
        title=title, artist="A", uploaded_by_id=uploader_id
    )


async def test_add_idempotent(session: AsyncSession) -> None:
    user = await _make_user(session, telegram_id=701)
    track = await _make_track(session, user.id)

    repo = UserTrackLibraryRepository(session)
    added_first = await repo.add(user.id, track.id, source="upload")
    added_second = await repo.add(user.id, track.id, source="upload")

    assert added_first is True
    assert added_second is False


async def test_two_users_one_track(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, telegram_id=702)
    u2 = await _make_user(session, telegram_id=703)
    track = await _make_track(session, u1.id)

    repo = UserTrackLibraryRepository(session)
    await repo.add(u1.id, track.id, source="upload")
    await repo.add(u2.id, track.id, source="yandex_music")

    u1_tracks, u1_total = await repo.list_by_user(u1.id)
    u2_tracks, u2_total = await repo.list_by_user(u2.id)
    assert u1_total == 1
    assert u2_total == 1
    assert u1_tracks[0].id == track.id
    assert u2_tracks[0].id == track.id


async def test_list_orders_by_imported_at_desc(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=704)
    t_old = await _make_track(session, user.id, title="old")
    t_new = await _make_track(session, user.id, title="new")

    repo = UserTrackLibraryRepository(session)
    await repo.add(user.id, t_old.id, source="upload")
    await session.flush()
    await repo.add(user.id, t_new.id, source="upload")

    tracks, total = await repo.list_by_user(user.id)
    assert total == 2
    assert tracks[0].id == t_new.id
    assert tracks[1].id == t_old.id


async def test_list_includes_owned_track_without_library_row(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=714)
    track = await _make_track(session, user.id, title="owned")

    repo = UserTrackLibraryRepository(session)
    tracks, total = await repo.list_by_user(user.id)

    assert total == 1
    assert [t.id for t in tracks] == [track.id]


async def test_list_excludes_external_owner_marker_without_library_row(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=718)
    track_repo = TrackRepository(session)
    track = await track_repo.create(
        title="External",
        artist="A",
        uploaded_by_id=user.id,
        source="soundcloud",
        source_platform="soundcloud",
        imported_from="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
    )

    repo = UserTrackLibraryRepository(session)
    tracks, total = await repo.list_by_user(user.id)

    assert total == 0
    assert track.id not in [t.id for t in tracks]


async def test_count_includes_owned_track_without_library_row(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=715)
    await _make_track(session, user.id, title="owned")

    repo = UserTrackLibraryRepository(session)

    assert await repo.count_by_user(user.id) == 1


async def test_list_liked_or_imported_uses_library_source_for_local_match(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session, telegram_id=719)
    importer = await _make_user(session, telegram_id=720)
    track = await _make_track(session, owner.id, title="Local")
    repo = UserTrackLibraryRepository(session)
    await repo.add(importer.id, track.id, source="yandex_music")

    tracks, total = await repo.list_liked_or_imported(importer.id)

    assert total == 1
    assert [t.id for t in tracks] == [track.id]


async def test_owned_track_not_duplicated_by_other_user_library(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session, telegram_id=716)
    other = await _make_user(session, telegram_id=717)
    track = await _make_track(session, owner.id, title="shared")

    repo = UserTrackLibraryRepository(session)
    await repo.add(other.id, track.id, source="telegram")

    tracks, total = await repo.list_by_user(owner.id)

    assert total == 1
    assert [t.id for t in tracks] == [track.id]


async def test_remove(session: AsyncSession) -> None:
    user = await _make_user(session, telegram_id=705)
    track = await _make_track(session, user.id)
    repo = UserTrackLibraryRepository(session)
    await repo.add(user.id, track.id, source="upload")

    removed = await repo.remove(user.id, track.id)
    not_removed = await repo.remove(user.id, track.id)
    assert removed is True
    assert not_removed is False


async def test_count_by_user(session: AsyncSession) -> None:
    user = await _make_user(session, telegram_id=706)
    t1 = await _make_track(session, user.id, title="a")
    t2 = await _make_track(session, user.id, title="b")
    repo = UserTrackLibraryRepository(session)
    await repo.add(user.id, t1.id)
    await repo.add(user.id, t2.id)

    assert await repo.count_by_user(user.id) == 2


async def test_has(session: AsyncSession) -> None:
    user = await _make_user(session, telegram_id=707)
    t = await _make_track(session, user.id)
    repo = UserTrackLibraryRepository(session)

    assert await repo.has(user.id, t.id) is False
    await repo.add(user.id, t.id)
    assert await repo.has(user.id, t.id) is True
