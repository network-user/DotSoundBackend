from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.models.dislike import Dislike
from app.models.like import Like
from app.models.listen_event import ListenEvent
from app.models.track import Track
from app.models.user import User
from app.services.track_features_builder import (
    WINDOW_DAYS,
    build_track_features,
)

pytestmark = pytest.mark.anyio


async def _make_user(
    session: AsyncSession,
    telegram_id: int,
) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name="U",
    )
    session.add(user)
    await session.flush()
    return user


async def _make_track(
    session: AsyncSession,
    *,
    title: str = "T",
    genre: str | None = "rock",
    play_count: int = 0,
    source: str = "internal",
) -> Track:
    track = Track(
        title=title,
        genre=genre,
        play_count=play_count,
        source=source,
        file_key="k",
    )
    session.add(track)
    await session.flush()
    return track


async def _make_artist(
    session: AsyncSession,
    name: str,
) -> Artist:
    artist = Artist(name=name, name_normalized=name.lower())
    session.add(artist)
    await session.flush()
    return artist


async def _add_listen(
    session: AsyncSession,
    *,
    user_id: int,
    track_id: int,
    duration: int = 100,
    total: int | None = 200,
    completed: bool = False,
    skipped: bool = False,
    created_at: datetime | None = None,
) -> None:
    now = datetime.now(UTC)
    event = ListenEvent(
        user_id=user_id,
        track_id=track_id,
        started_at=created_at or now,
        duration_listened_seconds=duration,
        total_duration_seconds=total,
        completed=completed,
        skipped=skipped,
        created_at=created_at or now,
    )
    session.add(event)
    await session.flush()


async def test_empty_input_returns_empty(
    session: AsyncSession,
) -> None:
    result = await build_track_features(session, [])
    assert result == []


async def test_single_track_basic_fields(
    session: AsyncSession,
) -> None:
    track = await _make_track(
        session,
        title="hello",
        genre="pop",
        play_count=42,
        source="internal",
    )

    result = await build_track_features(session, [track])

    assert len(result) == 1
    feat = result[0]
    assert feat.track_id == track.id
    assert feat.genre == "pop"
    assert feat.play_count == 42
    assert feat.source == "internal"
    assert feat.artist_ids == []
    assert feat.like_count == 0
    assert feat.dislike_count == 0
    assert feat.unique_listener_count == 0
    assert feat.completion_rate_7d is None
    assert feat.skip_rate_7d is None
    assert feat.mood_tags == []
    assert feat.audio_feature_vector is None


async def test_artist_mapping(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    a1 = await _make_artist(session, "A1")
    a2 = await _make_artist(session, "A2")
    session.add(
        TrackArtist(track_id=track.id, artist_id=a1.id)
    )
    session.add(
        TrackArtist(track_id=track.id, artist_id=a2.id)
    )
    await session.flush()

    result = await build_track_features(session, [track])
    assert sorted(result[0].artist_ids) == sorted(
        [a1.id, a2.id]
    )


async def test_like_dislike_counts(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    u1 = await _make_user(session, 1)
    u2 = await _make_user(session, 2)
    u3 = await _make_user(session, 3)

    session.add(Like(user_id=u1.id, track_id=track.id))
    session.add(Like(user_id=u2.id, track_id=track.id))
    session.add(Dislike(user_id=u3.id, track_id=track.id))
    await session.flush()

    result = await build_track_features(session, [track])
    assert result[0].like_count == 2
    assert result[0].dislike_count == 1


async def test_completion_and_skip_rates(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    u1 = await _make_user(session, 10)
    u2 = await _make_user(session, 11)

    await _add_listen(
        session,
        user_id=u1.id,
        track_id=track.id,
        completed=True,
    )
    await _add_listen(
        session,
        user_id=u1.id,
        track_id=track.id,
        completed=True,
    )
    await _add_listen(
        session,
        user_id=u2.id,
        track_id=track.id,
        skipped=True,
    )
    await _add_listen(
        session,
        user_id=u2.id,
        track_id=track.id,
    )

    result = await build_track_features(session, [track])
    feat = result[0]
    assert feat.unique_listener_count == 2
    assert feat.completion_rate_7d == pytest.approx(0.5)
    assert feat.skip_rate_7d == pytest.approx(0.25)


async def test_old_listens_excluded_from_window(
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    u1 = await _make_user(session, 20)

    old = datetime.now(UTC) - timedelta(
        days=WINDOW_DAYS + 1
    )
    await _add_listen(
        session,
        user_id=u1.id,
        track_id=track.id,
        completed=True,
        created_at=old,
    )

    result = await build_track_features(session, [track])
    feat = result[0]
    assert feat.unique_listener_count == 0
    assert feat.completion_rate_7d is None
    assert feat.skip_rate_7d is None


async def test_multi_track_isolation(
    session: AsyncSession,
) -> None:
    t1 = await _make_track(session, title="t1")
    t2 = await _make_track(session, title="t2")
    u1 = await _make_user(session, 30)

    session.add(Like(user_id=u1.id, track_id=t1.id))
    await _add_listen(
        session,
        user_id=u1.id,
        track_id=t2.id,
        skipped=True,
    )
    await session.flush()

    result = await build_track_features(
        session, [t1, t2]
    )
    by_id = {f.track_id: f for f in result}
    assert by_id[t1.id].like_count == 1
    assert by_id[t1.id].skip_rate_7d is None
    assert by_id[t2.id].like_count == 0
    assert by_id[t2.id].skip_rate_7d == pytest.approx(1.0)
