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


async def test_list_active_hides_youtube_tracks(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    repo = TrackRepository(session)
    await repo.create(
        title="Visible",
        artist="A",
        uploaded_by_id=user.id,
        source_platform="soundcloud",
    )
    await repo.create(
        title="Hidden",
        artist="A",
        uploaded_by_id=user.id,
        source_platform="youtube",
        imported_from="youtube",
    )

    tracks, total = await repo.list_active(offset=0, limit=20)

    assert total == 1
    assert len(tracks) == 1
    assert tracks[0].title == "Visible"


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
    assert result.deleted_at is not None
    assert result.deleted_by_id == user.id
    assert result.deleted_reason == "owner"


async def test_delete_by_owner_refuses_external_reference(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=41)
    repo = TrackRepository(session)
    track = await repo.create(
        title="External",
        artist="A",
        uploaded_by_id=user.id,
        source="soundcloud",
        source_platform="soundcloud",
        imported_from="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
    )

    result = await repo.delete_by_owner(track.id, user.id)

    assert result is None
    await session.refresh(track)
    assert track.is_active is True
    assert track.deleted_at is None


async def test_get_access_info_allows_public_ownerless_external(
    session: AsyncSession,
) -> None:
    repo = TrackRepository(session)
    track = await repo.create(
        title="Public External",
        artist="A",
        source="soundcloud",
        source_platform="soundcloud",
        imported_from="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        uploaded_by_id=None,
        is_public=True,
    )

    access = await repo.get_access_info(track.id)

    assert access == (True, None)


async def test_delete_by_owner_idempotent(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=42)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Idem",
        artist="A",
        uploaded_by_id=user.id,
    )
    first = await repo.delete_by_owner(track.id, user.id)
    assert first is not None
    second = await repo.delete_by_owner(track.id, user.id)
    assert second is None


async def test_restore_by_owner_undoes_soft_delete(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=43)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Resto",
        artist="A",
        uploaded_by_id=user.id,
    )
    await repo.delete_by_owner(track.id, user.id)
    restored = await repo.restore_by_owner(track.id, user.id)
    assert restored is not None
    assert restored.is_active is True
    assert restored.deleted_at is None
    assert restored.deleted_by_id is None
    assert restored.deleted_reason is None


async def test_restore_by_owner_refuses_admin_deleted(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=44)
    admin = await _make_user(session, telegram_id=45)
    repo = TrackRepository(session)
    track = await repo.create(
        title="DMCA",
        artist="A",
        uploaded_by_id=user.id,
    )
    await repo.admin_soft_delete(
        track.id, by_user_id=admin.id, reason="dmca"
    )
    out = await repo.restore_by_owner(track.id, user.id)
    assert out is None


async def test_restore_by_owner_refuses_external_reference(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=4500)
    repo = TrackRepository(session)
    track = await repo.create(
        title="External deleted",
        artist="A",
        uploaded_by_id=user.id,
        source="soundcloud",
        source_platform="soundcloud",
        imported_from="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
    )
    await repo.admin_soft_delete(
        track.id, by_user_id=user.id, reason="owner"
    )

    out = await repo.restore_by_owner(track.id, user.id)

    assert out is None
    await session.refresh(track)
    assert track.deleted_at is not None


async def test_list_imported_by_user_uses_library_link(
    session: AsyncSession,
) -> None:
    owner = await _make_user(session, telegram_id=4501)
    importer = await _make_user(session, telegram_id=4502)
    repo = TrackRepository(session)
    track = await repo.create(
        title="Linked Import",
        artist="A",
        uploaded_by_id=owner.id,
        source="soundcloud",
        source_platform="soundcloud",
        imported_from="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
    )
    from app.repositories.user_track_library import (
        UserTrackLibraryRepository,
    )

    library = UserTrackLibraryRepository(session)
    await library.add(importer.id, track.id, source="yandex_music")

    rows, total = await repo.list_imported_by_user(importer.id)
    filtered, filtered_total = await repo.list_imported_by_user(
        importer.id,
        source_filter="yandex_music",
    )

    assert total == 1
    assert [t.id for t in rows] == [track.id]
    assert filtered_total == 1
    assert [t.id for t in filtered] == [track.id]


async def test_list_user_trash_only_owners_owner_reason(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=46)
    admin = await _make_user(session, telegram_id=47)
    repo = TrackRepository(session)
    own = await repo.create(
        title="Own",
        artist="A",
        uploaded_by_id=user.id,
    )
    admin_hidden = await repo.create(
        title="AdminHidden",
        artist="A",
        uploaded_by_id=user.id,
    )
    external = await repo.create(
        title="ExternalHidden",
        artist="A",
        uploaded_by_id=user.id,
        source="soundcloud",
        source_platform="soundcloud",
        imported_from="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
    )
    await repo.delete_by_owner(own.id, user.id)
    await repo.admin_soft_delete(
        admin_hidden.id, by_user_id=admin.id, reason="admin"
    )
    await repo.admin_soft_delete(
        external.id, by_user_id=user.id, reason="owner"
    )
    rows, total = await repo.list_user_trash(user.id)
    ids = {t.id for t in rows}
    assert total == 1
    assert own.id in ids
    assert admin_hidden.id not in ids
    assert external.id not in ids


async def test_list_hard_delete_candidates_only_deleted(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=48)
    repo = TrackRepository(session)
    alive = await repo.create(
        title="Alive",
        artist="A",
        uploaded_by_id=user.id,
    )
    dead = await repo.create(
        title="Dead",
        artist="A",
        uploaded_by_id=user.id,
    )
    await repo.delete_by_owner(dead.id, user.id)
    rows = await repo.list_hard_delete_candidates(limit=10)
    ids = [t.id for t in rows]
    assert dead.id in ids
    assert alive.id not in ids


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
