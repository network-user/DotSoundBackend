from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.models.artist_monthly_stats import ArtistMonthlyStats
from app.repositories.artist_stats import ArtistStatsRepository
from app.services.artist_stats_service import ArtistStatsService

pytestmark = pytest.mark.anyio


async def _make_artist(
    session: AsyncSession, name: str = "Test"
) -> Artist:
    a = Artist(name=name, name_normalized=name.lower())
    session.add(a)
    await session.flush()
    await session.refresh(a)
    return a


async def _make_snapshot(
    session: AsyncSession,
    artist_id: int,
    year: int,
    month: int,
    unique_listeners: int = 0,
    total_plays: int = 0,
    total_likes: int = 0,
    total_followers: int = 0,
) -> ArtistMonthlyStats:
    row = ArtistMonthlyStats(
        artist_id=artist_id,
        year=year,
        month=month,
        unique_listeners=unique_listeners,
        total_plays=total_plays,
        total_likes=total_likes,
        total_followers=total_followers,
        snapshotted_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# get_latest_listeners_batch
# ---------------------------------------------------------------------------


async def test_get_latest_listeners_batch_empty_ids(
    session: AsyncSession,
) -> None:
    repo = ArtistStatsRepository(session)
    result = await repo.get_latest_listeners_batch([])
    assert result == {}


async def test_get_latest_listeners_batch_no_snapshots(
    session: AsyncSession,
) -> None:
    artist = await _make_artist(session)
    repo = ArtistStatsRepository(session)
    result = await repo.get_latest_listeners_batch([artist.id])
    assert result == {}


async def test_get_latest_listeners_batch_picks_latest(
    session: AsyncSession,
) -> None:
    artist = await _make_artist(session)
    await _make_snapshot(session, artist.id, 2024, 11, unique_listeners=50)
    await _make_snapshot(session, artist.id, 2025, 1, unique_listeners=200)
    await _make_snapshot(session, artist.id, 2024, 12, unique_listeners=100)

    repo = ArtistStatsRepository(session)
    result = await repo.get_latest_listeners_batch([artist.id])
    assert result == {artist.id: 200}


async def test_get_latest_listeners_batch_multiple_artists(
    session: AsyncSession,
) -> None:
    a1 = await _make_artist(session, "Alpha")
    a2 = await _make_artist(session, "Beta")
    a3 = await _make_artist(session, "Gamma")

    await _make_snapshot(session, a1.id, 2025, 3, unique_listeners=10)
    await _make_snapshot(session, a1.id, 2025, 4, unique_listeners=20)
    await _make_snapshot(session, a2.id, 2025, 2, unique_listeners=99)
    # a3 has no snapshots

    repo = ArtistStatsRepository(session)
    result = await repo.get_latest_listeners_batch(
        [a1.id, a2.id, a3.id]
    )
    assert result[a1.id] == 20
    assert result[a2.id] == 99
    assert a3.id not in result


async def test_get_latest_listeners_batch_unknown_ids(
    session: AsyncSession,
) -> None:
    repo = ArtistStatsRepository(session)
    result = await repo.get_latest_listeners_batch([999_999])
    assert result == {}


# ---------------------------------------------------------------------------
# upsert_snapshot
# ---------------------------------------------------------------------------


async def test_upsert_snapshot_creates(
    session: AsyncSession,
) -> None:
    artist = await _make_artist(session)
    repo = ArtistStatsRepository(session)

    await repo.upsert_snapshot(
        artist.id, 2025, 5,
        unique_listeners=42,
        total_plays=100,
        total_likes=10,
        total_followers=5,
    )

    assert await repo.has_snapshot(artist.id, 2025, 5)
    history = await repo.get_history(artist.id)
    assert len(history) == 1
    assert history[0].unique_listeners == 42


async def test_upsert_snapshot_updates(
    session: AsyncSession,
) -> None:
    artist = await _make_artist(session)
    await _make_snapshot(session, artist.id, 2025, 5, unique_listeners=10)

    repo = ArtistStatsRepository(session)
    await repo.upsert_snapshot(
        artist.id, 2025, 5, unique_listeners=99
    )

    history = await repo.get_history(artist.id)
    assert len(history) == 1
    assert history[0].unique_listeners == 99


# ---------------------------------------------------------------------------
# has_snapshot
# ---------------------------------------------------------------------------


async def test_has_snapshot_true(session: AsyncSession) -> None:
    artist = await _make_artist(session)
    await _make_snapshot(session, artist.id, 2025, 6)
    repo = ArtistStatsRepository(session)
    assert await repo.has_snapshot(artist.id, 2025, 6) is True


async def test_has_snapshot_false(session: AsyncSession) -> None:
    artist = await _make_artist(session)
    repo = ArtistStatsRepository(session)
    assert await repo.has_snapshot(artist.id, 2025, 6) is False


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


async def test_get_history_sorted_newest_first(
    session: AsyncSession,
) -> None:
    artist = await _make_artist(session)
    await _make_snapshot(session, artist.id, 2025, 1, unique_listeners=1)
    await _make_snapshot(session, artist.id, 2025, 3, unique_listeners=3)
    await _make_snapshot(session, artist.id, 2025, 2, unique_listeners=2)

    repo = ArtistStatsRepository(session)
    history = await repo.get_history(artist.id)

    assert [r.month for r in history] == [3, 2, 1]


async def test_get_history_empty(session: AsyncSession) -> None:
    artist = await _make_artist(session)
    repo = ArtistStatsRepository(session)
    assert await repo.get_history(artist.id) == []


# ---------------------------------------------------------------------------
# ArtistStatsService.snapshot_all_artists
# ---------------------------------------------------------------------------


async def test_snapshot_all_artists_no_artists(
    session: AsyncSession,
) -> None:
    svc = ArtistStatsService(session)
    saved = await svc.snapshot_all_artists()
    assert saved == 0


async def test_snapshot_all_artists_creates_snapshots(
    session: AsyncSession,
) -> None:
    a1 = await _make_artist(session, "Band A")
    a2 = await _make_artist(session, "Band B")

    svc = ArtistStatsService(session)
    # Pin the "previous month" to 2025-04 so snapshots go there
    with patch.object(
        svc, "_prev_ym", return_value=(2025, 4)
    ):
        saved = await svc.snapshot_all_artists()

    assert saved == 2
    repo = ArtistStatsRepository(session)
    assert await repo.has_snapshot(a1.id, 2025, 4)
    assert await repo.has_snapshot(a2.id, 2025, 4)


async def test_snapshot_all_artists_is_idempotent(
    session: AsyncSession,
) -> None:
    artist = await _make_artist(session)
    svc = ArtistStatsService(session)

    with patch.object(svc, "_prev_ym", return_value=(2025, 3)):
        await svc.snapshot_all_artists()
        saved = await svc.snapshot_all_artists()

    assert saved == 1
    repo = ArtistStatsRepository(session)
    history = await repo.get_history(artist.id)
    assert len(history) == 1
