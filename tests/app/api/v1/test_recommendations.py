from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.models.artist_follow import ArtistFollow
from app.models.like import Like
from app.models.track_similarity import TrackSimilarity
from tests.conftest import (
    auth_headers,
    create_test_user,
)
from tests.factories import TrackFactory

pytestmark = pytest.mark.anyio


async def test_home_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/home"
    )
    assert r.status_code == 401


async def test_home_empty(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7001)
    headers = await auth_headers(client, 7001)

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "sections" in data
    assert "highlights" in data
    assert "maturity" in data


async def test_home_highlights_populated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Setup: create some tracks and listens to trigger highlights
    user_id = 7003
    await create_test_user(client, user_id)
    headers = await auth_headers(client, user_id)

    # Create a track
    from tests.factories import TrackFactory
    track = TrackFactory.create(file_key="continue.mp3")
    db_session.add(track)
    await db_session.commit()

    # Create an incomplete listen event for this track
    from datetime import UTC, datetime

    from app.models.listen_event import ListenEvent
    listen = ListenEvent(
        user_id=1,  # Fixed ID for the first user in tests
        track_id=track.id,
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        duration_listened_seconds=10,
        completed=False,
        skipped=False,
    )
    db_session.add(listen)
    await db_session.commit()

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["highlights"]) > 0
    assert data["highlights"][0]["track"]["id"] == track.id
    assert data["highlights"][0]["label"] == "Продолжить"


async def test_home_returns_sections(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7002)
    headers = await auth_headers(client, 7002)

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["sections"], list)
    assert data["maturity"] in [
        "cold",
        "warm",
        "calibrated",
        "enriched",
        "personalized",
    ]


async def test_home_uses_followed_artist_signal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 70301)
    headers = await auth_headers(client, user["id"])
    artist = Artist(name="Followed Artist", name_normalized="followed artist")
    track = TrackFactory.create(
        title="Followed Track",
        artist="Followed Artist",
        file_key="followed.mp3",
        play_count=10,
    )
    db_session.add_all([artist, track])
    await db_session.flush()
    db_session.add(TrackArtist(track_id=track.id, artist_id=artist.id))
    db_session.add(
        ArtistFollow(user_id=user["id"], artist_id=artist.id)
    )
    await db_session.commit()

    r = await client.get(
        "/api/v1/recommendations/home",
        headers=headers,
    )

    assert r.status_code == 200
    fav = [
        section
        for section in r.json()["sections"]
        if section["section_type"] == "fav_artists"
    ]
    assert fav
    assert track.id in {item["id"] for item in fav[0]["tracks"]}


async def test_similar_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/similar/99999"
    )
    assert r.status_code == 200
    assert r.json()["tracks"] == []


async def test_similar_uses_similarity_index(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    seed = TrackFactory.create(
        title="Seed",
        genre="rock",
        file_key="seed.mp3",
    )
    similar = TrackFactory.create(
        title="Indexed Similar",
        genre="jazz",
        file_key="similar.mp3",
    )
    db_session.add_all([seed, similar])
    await db_session.flush()
    db_session.add(
        TrackSimilarity(
            track_id=seed.id,
            similar_track_id=similar.id,
            score=0.95,
            feature_version="v1",
        )
    )
    await db_session.commit()

    r = await client.get(
        f"/api/v1/recommendations/similar/{seed.id}?limit=1"
    )

    assert r.status_code == 200
    body = r.json()
    assert body["tracks"]
    assert body["tracks"][0]["id"] == similar.id


async def test_daily_mix(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7004)
    headers = await auth_headers(client, 7004)

    r = await client.get(
        "/api/v1/recommendations/daily-mix",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data


async def test_user_choice_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/user-choice"
    )
    assert r.status_code == 401


async def test_user_choice_ok(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7006)
    headers = await auth_headers(client, 7006)
    r = await client.get(
        "/api/v1/recommendations/user-choice?limit=10",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data
    assert "score_version" in data
    assert isinstance(
        data["tracks"],
        list,
    )


async def test_radio_missing_seed(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7005)
    headers = await auth_headers(client, 7005)

    r = await client.get(
        "/api/v1/recommendations/radio",
        headers=headers,
    )
    assert r.status_code == 422


async def test_radio_uses_seed_similarity_index(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 70302)
    headers = await auth_headers(client, user["id"])
    seed = TrackFactory.create(
        title="Radio Seed",
        genre="rock",
        file_key="radio-seed.mp3",
    )
    similar = TrackFactory.create(
        title="Radio Similar",
        genre="jazz",
        file_key="radio-similar.mp3",
    )
    db_session.add_all([seed, similar])
    await db_session.flush()
    db_session.add(
        TrackSimilarity(
            track_id=seed.id,
            similar_track_id=similar.id,
            score=0.98,
            feature_version="v1",
        )
    )
    await db_session.commit()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.lpush = AsyncMock(return_value=1)
    redis.ltrim = AsyncMock(return_value="OK")
    redis.expire = AsyncMock(return_value=True)

    with patch(
        "app.services.recommendation_service.get_redis_client",
        return_value=redis,
    ):
        r = await client.get(
            f"/api/v1/recommendations/radio?seed_track_id={seed.id}"
            "&queue_size=1",
            headers=headers,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["tracks"]
    assert body["tracks"][0]["id"] == similar.id


async def test_weekly_top_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/weekly-top"
    )
    assert r.status_code == 401


async def test_weekly_top_ok(
    client: AsyncClient,
) -> None:
    await create_test_user(client, 7007)
    headers = await auth_headers(client, 7007)
    r = await client.get(
        "/api/v1/recommendations/weekly-top?limit=20",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data
    assert "expires_at" in data
    assert "score_version" in data
    assert "window_days" in data
    assert data["window_days"] == 7
    assert isinstance(data["tracks"], list)


async def test_forgotten_treasures_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/recommendations/forgotten-treasures",
    )
    assert r.status_code == 401


async def test_forgotten_treasures_ok(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 70209)
    headers = await auth_headers(client, user["id"])
    track = TrackFactory.create(file_key="k/ft.mp3")
    db_session.add(track)
    await db_session.commit()

    liked_at = datetime.now(UTC) - timedelta(days=60)
    db_session.add(
        Like(
            user_id=user["id"],
            track_id=track.id,
            created_at=liked_at,
        )
    )
    await db_session.commit()

    r = await client.get(
        "/api/v1/recommendations/forgotten-treasures?limit=25",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert "generated_at" in data
    assert "expires_at" in data
    assert "score_version" in data
    assert "min_like_age_days" in data
    assert "silence_days" in data
    assert isinstance(data["tracks"], list)
    assert len(data["tracks"]) == 1
    assert data["tracks"][0]["id"] == track.id
