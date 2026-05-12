import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.artist import ArtistRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.artist_service import (
    ArtistService,
)

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
    title: str = "T",
    artist: str | None = "Drake",
    owner_id: int | None = None,
) -> int:
    repo = TrackRepository(session)
    track = await repo.create(
        title=title,
        artist=artist,
        file_key="k",
        uploaded_by_id=owner_id,
    )
    return track.id


async def test_resolve_and_link_creates_artist(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(
        db_session, owner_id=uid
    )

    svc = ArtistService(db_session)
    artists = await svc.resolve_and_link(
        track_id=tid,
        raw_artist_string="Drake",
    )

    assert len(artists) == 1
    assert artists[0].name == "Drake"
    assert artists[0].name_normalized == "drake"


async def test_resolve_feat(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(
        db_session, owner_id=uid
    )

    svc = ArtistService(db_session)
    artists = await svc.resolve_and_link(
        track_id=tid,
        raw_artist_string=(
            "Drake feat. Rihanna"
        ),
    )

    assert len(artists) == 2


async def test_resolve_dedup_duplicate_artist_in_one_string(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(
        db_session, owner_id=uid
    )
    svc = ArtistService(db_session)
    artists = await svc.resolve_and_link(
        tid, "Drake feat. Drake"
    )
    assert len(artists) == 1
    tarts = await svc.get_track_artists(tid)
    assert len(tarts) == 1


async def test_find_or_create_uses_canonical_row_when_normalized_dupes(
    db_session: AsyncSession,
) -> None:
    repo = ArtistRepository(db_session)
    first = await repo.create(
        name="Drake",
        name_normalized="drake",
        source="internal",
        external_id=None,
    )
    second = await repo.create(
        name="DRAKE",
        name_normalized="drake",
        source="internal",
        external_id=None,
    )
    assert first.id != second.id

    svc = ArtistService(db_session)
    got = await svc.find_or_create_by_name("Drake")
    assert got is not None
    assert got.id == min(first.id, second.id)


async def test_dedup_same_artist(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid1 = await _make_track(
        db_session,
        title="Song1",
        owner_id=uid,
    )
    tid2 = await _make_track(
        db_session,
        title="Song2",
        owner_id=uid,
    )

    svc = ArtistService(db_session)
    a1 = await svc.resolve_and_link(
        tid1, "Drake"
    )
    a2 = await svc.resolve_and_link(
        tid2, "Drake"
    )

    assert a1[0].id == a2[0].id


async def test_search(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(
        db_session, owner_id=uid
    )

    svc = ArtistService(db_session)
    await svc.resolve_and_link(tid, "Drake")

    results = await svc.search("dra")
    assert len(results) >= 1
    assert results[0].name == "Drake"


async def test_get_track_artists(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid = await _make_track(
        db_session, owner_id=uid
    )

    svc = ArtistService(db_session)
    await svc.resolve_and_link(
        tid, "Eminem feat. Dr. Dre"
    )

    artists = await svc.get_track_artists(tid)
    assert len(artists) >= 2


async def test_artist_detail_track_count_matches_list_after_delete(
    db_session: AsyncSession,
) -> None:
    from app.api.v1.artists import _build_artist_detail

    uid = await _make_user(db_session)
    tid_keep = await _make_track(
        db_session, title="Keep", owner_id=uid
    )
    tid_drop = await _make_track(
        db_session, title="Drop", owner_id=uid
    )
    svc = ArtistService(db_session)
    first = await svc.resolve_and_link(
        tid_keep, "ZetaArtistCountSync",
    )
    await svc.resolve_and_link(tid_drop, "ZetaArtistCountSync")
    artist_id = first[0].id

    _, listed_total = await svc.list_artist_tracks(
        artist_id, page=1, size=20
    )
    detail = await _build_artist_detail(db_session, artist_id)
    assert detail.track_count == listed_total

    await TrackRepository(db_session).delete_by_owner(
        tid_drop, uid
    )
    await db_session.flush()

    _, after_total = await svc.list_artist_tracks(
        artist_id, page=1, size=20
    )
    detail_after = await _build_artist_detail(
        db_session, artist_id
    )
    assert after_total == 1
    assert detail_after.track_count == 1
    assert detail_after.track_count == after_total


async def test_list_artist_tracks_includes_featured_credits(
    db_session: AsyncSession,
) -> None:
    uid = await _make_user(db_session)
    tid_collab = await _make_track(
        db_session, title="Collab", owner_id=uid
    )
    tid_solo = await _make_track(
        db_session, title="Solo", owner_id=uid
    )

    svc = ArtistService(db_session)
    await svc.resolve_and_link(
        tid_collab, "AlphaName feat. BetaName"
    )
    await svc.resolve_and_link(tid_solo, "BetaName")

    beta_id = (await svc.get_track_artists(tid_solo))[0].id
    tracks_b, total_b = await svc.list_artist_tracks(
        beta_id, page=1, size=20
    )
    assert total_b == 2
    assert len(tracks_b) == 2
    assert {t.id for t in tracks_b} == {
        tid_collab,
        tid_solo,
    }

    alpha_id = (await svc.get_track_artists(tid_collab))[0].id
    tracks_a, total_a = await svc.list_artist_tracks(
        alpha_id, page=1, size=20
    )
    assert total_a == 1
    assert tracks_a[0].id == tid_collab
