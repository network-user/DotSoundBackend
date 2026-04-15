import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
