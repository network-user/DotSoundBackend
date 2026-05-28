import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotsound_private_core.services.recommendation_engine import (
    ScoredTrack,
    TrackFeatures,
    UserPrefs,
    build_radio_queue,
    interleave_personalized_by_familiarity,
    score_tracks_for_user,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.recommendation_service import (
    RecommendationService,
    _midnight_ttl,
    _weekly_ttl,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.recommendation_service"


def test_midnight_ttl_positive() -> None:
    ttl = _midnight_ttl()
    assert ttl > 0
    assert ttl <= 86400


def test_weekly_ttl_positive() -> None:
    ttl = _weekly_ttl()
    assert ttl > 0
    assert ttl <= 7 * 86400


async def test_get_global_top_cached(
    session: AsyncSession,
) -> None:
    cached_ids = json.dumps([1, 2, 3])
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached_ids)

    mock_repo = AsyncMock()
    mock_repo.get_tracks_by_ids = AsyncMock(
        return_value=[]
    )

    with (
        patch(f"{_MOD}.get_redis_client", return_value=mock_redis),
        patch(
            "app.services.recommendation_service.RecommendationRepository",
            return_value=mock_repo,
        ),
    ):
        svc = RecommendationService(session)
        await svc.get_global_top()

    mock_repo.get_tracks_by_ids.assert_called_once_with(
        [1, 2, 3]
    )
    mock_redis.setex.assert_not_called()


async def test_get_global_top_cache_miss(
    session: AsyncSession,
) -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_track = MagicMock()
    mock_track.id = 10

    mock_repo = AsyncMock()
    mock_repo.get_popular_tracks = AsyncMock(
        return_value=[mock_track]
    )

    with (
        patch(f"{_MOD}.get_redis_client", return_value=mock_redis),
        patch(
            "app.services.recommendation_service.RecommendationRepository",
            return_value=mock_repo,
        ),
    ):
        svc = RecommendationService(session)
        result = await svc.get_global_top()

    assert len(result) == 1
    mock_redis.setex.assert_called_once()


async def test_build_user_prefs_merges_behavioral_taste(
    session: AsyncSession,
) -> None:
    mock_prefs = MagicMock()
    mock_prefs.preferred_genres = ["ambient"]
    mock_prefs.preferred_artist_ids = [7]
    mock_prefs.preferred_moods = []

    svc = RecommendationService(session)
    svc._pref_repo.get_by_user_id = AsyncMock(return_value=mock_prefs)
    svc._rec_repo.get_liked_track_ids = AsyncMock(return_value=set())
    svc._rec_repo.get_user_genre_listen_aggregates = AsyncMock(
        return_value=[("rock", 5)]
    )
    svc._rec_repo.get_user_artist_listen_aggregates = AsyncMock(
        return_value=[(42, 5, 2)]
    )
    svc._rec_repo.get_repeat_listen_counts = AsyncMock(return_value={})
    svc._follow_repo.list_followed_artist_ids = AsyncMock(return_value=[99])
    svc._catalog_repo.get_similar_artist_recommendation_signals = AsyncMock(
        return_value=([], {})
    )
    svc._listen_repo.get_recent = AsyncMock(return_value=[])

    prefs, _locale = await svc._build_user_prefs(1)

    assert prefs.preferred_genres == ["ambient", "rock"]
    assert prefs.preferred_artist_ids == [7, 99, 42]
    assert prefs.followed_artist_ids == [99]
    assert prefs.behavior_genre_weights["rock"] == 1.0
    assert prefs.behavior_artist_weights[42] == 1.0
    svc._catalog_repo.get_similar_artist_recommendation_signals.assert_awaited_once_with(
        [7, 99, 42]
    )


async def test_scoring_candidates_include_similar_tracks_for_followed_artists(
    session: AsyncSession,
) -> None:
    svc = RecommendationService(session)
    track = SimpleNamespace(id=501)
    prefs = UserPrefs(
        preferred_genres=[],
        preferred_artist_ids=[99],
        similar_artist_ids=[],
        similar_artist_weights={},
        behavior_genre_weights={},
        behavior_artist_weights={},
        taste_audio_vector=None,
        preferred_moods=[],
        liked_track_ids=set(),
        disliked_track_ids=set(),
        implicit_dislike_track_ids=set(),
        onboarding_genre_preview_taps=[],
        language_affinity={},
    )
    svc._rec_repo.get_candidate_tracks = AsyncMock(return_value=[])
    svc._rec_repo.get_tracks_by_artist_ids = AsyncMock(return_value=[])
    svc._rec_repo.get_track_similarity_candidates_for_artist_ids = AsyncMock(
        return_value=[track]
    )
    svc._rec_repo.get_recent_candidate_tracks = AsyncMock(return_value=[])

    out = await svc._scoring_candidate_tracks(
        user_id=1,
        limit=20,
        genre_filter=None,
        user_prefs=prefs,
        user_locale=None,
    )

    assert out == [track]
    svc._rec_repo.get_track_similarity_candidates_for_artist_ids.assert_awaited_once_with(
        [99],
        limit=50,
        exclude_ids=None,
    )


async def test_get_daily_playlist_cached(
    session: AsyncSession,
) -> None:
    cached = json.dumps(
        {
            "internal_track_ids": [1],
            "external_suggestions": [],
            "global_top_ids": [2],
            "generated_at": datetime.now(UTC).isoformat(),
            "expires_at": datetime.now(UTC).isoformat(),
        }
    )
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached)

    with patch(
        f"{_MOD}.get_redis_client",
        return_value=mock_redis,
    ):
        svc = RecommendationService(session)
        payload = await svc.get_daily_playlist(user_id=1)

    assert payload["internal_track_ids"] == [1]
    mock_redis.setex.assert_not_called()


async def test_refresh_daily_playlist_deletes_keys(
    session: AsyncSession,
) -> None:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock()
    mock_redis.setex = AsyncMock()

    mock_prefs = MagicMock()
    mock_prefs.preferred_genres = []
    mock_prefs.preferred_artist_ids = []
    mock_prefs.preferred_moods = []
    mock_prefs.onboarding_completed = False
    mock_prefs.calibration_completed = False

    mock_pref_repo = AsyncMock()
    mock_pref_repo.get_by_user_id = AsyncMock(
        return_value=mock_prefs
    )
    mock_listen_repo = AsyncMock()
    mock_listen_repo.get_recent = AsyncMock(
        return_value=[]
    )
    mock_listen_repo.count_for_user = AsyncMock(
        return_value=0
    )
    mock_rec_repo = AsyncMock()
    mock_rec_repo.get_liked_track_ids = AsyncMock(
        return_value=set()
    )
    mock_rec_repo.get_candidate_tracks = AsyncMock(
        return_value=[]
    )
    mock_rec_repo.get_popular_tracks = AsyncMock(
        return_value=[]
    )
    mock_rec_repo.get_track_artist_map = AsyncMock(
        return_value={}
    )

    mock_discovery = AsyncMock()
    mock_discovery.discover = AsyncMock(return_value=[])

    with (
        patch(f"{_MOD}.get_redis_client", return_value=mock_redis),
        patch(
            "app.services.recommendation_service.PreferenceRepository",
            return_value=mock_pref_repo,
        ),
        patch(
            "app.services.recommendation_service.ListenEventRepository",
            return_value=mock_listen_repo,
        ),
        patch(
            "app.services.recommendation_service.RecommendationRepository",
            return_value=mock_rec_repo,
        ),
        patch(
            "app.services.external_discovery_service.ExternalDiscoveryService",
            return_value=mock_discovery,
        ),
        patch(
            "app.services.recommendation_service.build_daily_mix",
            return_value=[],
        ),
        patch(
            "app.services.recommendation_service.merge_hybrid_playlist",
            return_value=([], []),
        ),
    ):
        svc = RecommendationService(session)
        svc._session = AsyncMock()
        svc._session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                ),
                all=MagicMock(return_value=[]),
            )
        )
        await svc.refresh_daily_playlist(user_id=1)

    deleted_keys = [
        call.args[0]
        for call in mock_redis.delete.call_args_list
    ]
    assert "rec:daily:1" in deleted_keys


async def test_get_radio_guard_uses_last_queue(
    session: AsyncSession,
) -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)
    mock_redis.get = AsyncMock(
        return_value=json.dumps([11, 12])
    )
    mock_tracks = [
        SimpleNamespace(id=11),
        SimpleNamespace(id=12),
    ]

    with patch(
        f"{_MOD}.get_redis_client",
        return_value=mock_redis,
    ):
        svc = RecommendationService(session)
        svc._rec_repo.get_tracks_by_ids = AsyncMock(
            return_value=mock_tracks
        )
        out = await svc.get_radio(
            seed_track_id=5,
            user_id=77,
            exclude_ids=[1, 2],
        )

    assert [t.id for t in out] == [11, 12]
    svc._rec_repo.get_tracks_by_ids.assert_called_once_with(
        [11, 12]
    )


async def test_get_radio_guard_honors_exclude_ids(
    session: AsyncSession,
) -> None:
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)
    mock_redis.get = AsyncMock(
        return_value=json.dumps([11, 12])
    )
    mock_tracks = [
        SimpleNamespace(id=11),
        SimpleNamespace(id=12),
    ]

    with patch(
        f"{_MOD}.get_redis_client",
        return_value=mock_redis,
    ):
        svc = RecommendationService(session)
        svc._load_radio_session = AsyncMock(return_value=[])
        svc._rec_repo.get_tracks_by_ids = AsyncMock(
            return_value=mock_tracks
        )
        out = await svc.get_radio(
            seed_track_id=5,
            user_id=77,
            exclude_ids=[11],
        )

    assert [t.id for t in out] == [12]


async def test_get_radio_guard_filters_recent_playback_failures(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)
    mock_redis.get = AsyncMock(
        return_value=json.dumps([11, 12])
    )
    failed = SimpleNamespace(
        id=11,
        access_mode="third_party_stream",
        file_key=None,
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=now - timedelta(minutes=5),
    )
    playable = SimpleNamespace(
        id=12,
        access_mode="internal_stream",
        file_key="track.mp3",
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
    )

    with patch(
        f"{_MOD}.get_redis_client",
        return_value=mock_redis,
    ):
        svc = RecommendationService(session)
        svc._rec_repo.get_tracks_by_ids = AsyncMock(
            return_value=[failed, playable]
        )
        out = await svc.get_radio(
            seed_track_id=5,
            user_id=77,
        )

    assert [t.id for t in out] == [12]


async def test_get_radio_cache_key_depends_on_exclude_ids(
    session: AsyncSession,
) -> None:
    seed = SimpleNamespace(id=5)
    candidate = SimpleNamespace(id=21)
    feat_seed = SimpleNamespace(track_id=5)
    feat_candidate = SimpleNamespace(track_id=21)
    scored = [SimpleNamespace(track_id=21)]

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_track_repo = AsyncMock()
    mock_track_repo.get_by_id = AsyncMock(return_value=seed)

    with (
        patch(
            f"{_MOD}.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "app.repositories.track.TrackRepository",
            return_value=mock_track_repo,
        ),
        patch(
            f"{_MOD}.build_radio_queue",
            return_value=scored,
        ),
    ):
        svc = RecommendationService(session)
        svc._rec_repo.get_candidate_tracks = AsyncMock(
            return_value=[candidate]
        )
        svc._tracks_to_features = AsyncMock(
            return_value=[feat_seed, feat_candidate]
        )
        svc._telemetry.record_impressions = AsyncMock()

        await svc.get_radio(
            seed_track_id=5,
            user_id=77,
            exclude_ids=[100],
        )
        await svc.get_radio(
            seed_track_id=5,
            user_id=77,
            exclude_ids=[101],
        )

    cache_calls = [
        call.args[0]
        for call in mock_redis.setex.call_args_list
        if call.args[0].startswith("rec:radio:")
    ]
    assert len(cache_calls) >= 2
    assert cache_calls[-1] != cache_calls[-2]


async def test_get_radio_filters_recent_playback_failures(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    seed = SimpleNamespace(
        id=5,
        access_mode="internal_stream",
        file_key="seed.mp3",
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
    )
    playable = SimpleNamespace(
        id=21,
        access_mode="internal_stream",
        file_key="playable.mp3",
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
    )
    failed = SimpleNamespace(
        id=22,
        access_mode="third_party_stream",
        file_key=None,
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=now - timedelta(minutes=5),
    )
    feat_seed = SimpleNamespace(track_id=5)
    feat_playable = SimpleNamespace(track_id=21)
    scored = [SimpleNamespace(track_id=21)]

    mock_track_repo = AsyncMock()
    mock_track_repo.get_by_id = AsyncMock(return_value=seed)

    def fake_build_radio_queue(
        _seed: object,
        _history: list[object],
        candidates: list[object],
        _queue_size: int,
        **_kwargs: object,
    ) -> list[object]:
        assert [c.track_id for c in candidates] == [21]
        return scored

    mock_artist_repo = AsyncMock()
    mock_artist_repo.get_track_artists = AsyncMock(return_value=[])

    with (
        patch(
            "app.repositories.track.TrackRepository",
            return_value=mock_track_repo,
        ),
        patch(
            "app.repositories.artist.ArtistRepository",
            return_value=mock_artist_repo,
        ),
        patch(
            f"{_MOD}.build_radio_queue",
            side_effect=fake_build_radio_queue,
        ),
    ):
        svc = RecommendationService(session)
        svc._rec_repo.get_candidate_tracks = AsyncMock(
            return_value=[failed, playable]
        )
        svc._rec_repo.get_track_similarity_candidates = AsyncMock(
            return_value=[]
        )
        svc._embedding_repo.find_neighbors = AsyncMock(return_value=[])
        svc._tracks_to_features = AsyncMock(
            return_value=[feat_seed, feat_playable]
        )

        result = await svc.get_radio(seed_track_id=5, user_id=None)

    assert [t.id for t in result] == [21]


async def test_get_radio_filters_non_streamable_external_links(
    session: AsyncSession,
) -> None:
    seed = SimpleNamespace(
        id=5,
        access_mode="internal_stream",
        file_key="seed.mp3",
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
    )
    external_link = SimpleNamespace(
        id=22,
        access_mode="external_link",
        file_key=None,
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
    )

    mock_track_repo = AsyncMock()
    mock_track_repo.get_by_id = AsyncMock(return_value=seed)

    with patch(
        "app.repositories.track.TrackRepository",
        return_value=mock_track_repo,
    ):
        svc = RecommendationService(session)
        svc._rec_repo.get_candidate_tracks = AsyncMock(
            return_value=[external_link]
        )

        result = await svc.get_radio(seed_track_id=5, user_id=None)

    assert result == []


async def test_get_home_sections_cache_hit_batches_track_fetch(
    session: AsyncSession,
) -> None:
    cached_payload = json.dumps(
        {
            "sections": [
                {
                    "title": "Continue",
                    "section_type": "continue",
                    "track_ids": [1, 2],
                },
                {
                    "title": "Popular",
                    "section_type": "popular",
                    "track_ids": [2, 3],
                },
            ],
            "highlights": [
                {
                    "track_id": 1,
                    "label": "Continue",
                    "reason": "Resume",
                },
            ],
            "maturity": "warm",
        }
    )
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached_payload)
    mock_redis.setex = AsyncMock()

    track1 = SimpleNamespace(id=1)
    track2 = SimpleNamespace(id=2)
    track3 = SimpleNamespace(id=3)

    mock_track_repo = AsyncMock()
    mock_track_repo.get_by_ids_preserve_order = AsyncMock(
        return_value=[track1, track2, track3]
    )

    with (
        patch(f"{_MOD}.get_redis_client", return_value=mock_redis),
        patch(
            "app.repositories.track.TrackRepository",
            return_value=mock_track_repo,
        ),
    ):
        svc = RecommendationService(session)
        result = await svc.get_home_sections(user_id=42)

    mock_track_repo.get_by_ids_preserve_order.assert_called_once()
    fetched_ids = mock_track_repo.get_by_ids_preserve_order.call_args[0][0]
    assert set(fetched_ids) == {1, 2, 3}

    mock_redis.setex.assert_not_called()

    assert result["maturity"] == "warm"
    assert len(result["sections"]) == 2
    assert [t.id for t in result["sections"][0]["tracks"]] == [1, 2]
    assert [t.id for t in result["sections"][1]["tracks"]] == [2, 3]
    assert len(result["highlights"]) == 1
    assert result["highlights"][0]["track"].id == 1
    assert result["highlights"][0]["label"] == "Continue"


async def test_get_genre_mixes_cache_hit_uses_single_batch_fetch(
    session: AsyncSession,
) -> None:
    cached_payload = json.dumps(
        [
            {"genre": "rock", "title": "Rock", "track_ids": [1, 2]},
            {"genre": "pop", "title": "Pop", "track_ids": [3, 4]},
        ]
    )
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached_payload)

    tracks = [SimpleNamespace(id=i) for i in (1, 2, 3, 4)]

    mock_rec_repo = AsyncMock()
    mock_rec_repo.get_tracks_by_ids = AsyncMock(return_value=tracks)

    with (
        patch(f"{_MOD}.get_redis_client", return_value=mock_redis),
        patch(
            "app.services.recommendation_service.RecommendationRepository",
            return_value=mock_rec_repo,
        ),
    ):
        svc = RecommendationService(session)
        result = await svc.get_genre_mixes(user_id=42)

    mock_rec_repo.get_tracks_by_ids.assert_called_once()
    fetched_ids = mock_rec_repo.get_tracks_by_ids.call_args[0][0]
    assert set(fetched_ids) == {1, 2, 3, 4}

    assert len(result) == 2
    assert [t.id for t in result[0]["tracks"]] == [1, 2]
    assert [t.id for t in result[1]["tracks"]] == [3, 4]


async def test_get_radio_passes_station_neighbor_track_ids(
    session: AsyncSession,
) -> None:
    seed = SimpleNamespace(
        id=5,
        access_mode="internal_stream",
        file_key="seed.mp3",
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
        genre=None,
    )
    candidate = SimpleNamespace(
        id=21,
        access_mode="internal_stream",
        file_key="c.mp3",
        hls_manifest_key=None,
        playback_suppressed_until=None,
        playback_recovery_failed_at=None,
    )
    feat_seed = SimpleNamespace(track_id=5)
    feat_candidate = SimpleNamespace(track_id=21)
    scored = [SimpleNamespace(track_id=21)]

    mock_track_repo = AsyncMock()
    mock_track_repo.get_by_id = AsyncMock(return_value=seed)

    mock_artist_repo = AsyncMock()
    mock_artist_repo.get_track_artists = AsyncMock(
        return_value=[SimpleNamespace(id=900)]
    )

    captured: dict[str, object] = {}

    def fake_build_radio_queue(
        _seed: object,
        _history: list[object],
        _candidates: list[object],
        _queue_size: int,
        **kwargs: object,
    ) -> list[object]:
        captured["station_neighbor_track_ids"] = kwargs.get(
            "station_neighbor_track_ids"
        )
        return scored

    with (
        patch(
            "app.repositories.track.TrackRepository",
            return_value=mock_track_repo,
        ),
        patch(
            "app.repositories.artist.ArtistRepository",
            return_value=mock_artist_repo,
        ),
        patch(
            f"{_MOD}.build_radio_queue",
            side_effect=fake_build_radio_queue,
        ),
    ):
        svc = RecommendationService(session)
        svc._rec_repo.get_candidate_tracks = AsyncMock(
            return_value=[candidate]
        )
        svc._rec_repo.get_track_similarity_candidates = AsyncMock(
            return_value=[]
        )
        svc._embedding_repo.find_neighbors = AsyncMock(return_value=[])
        svc._catalog_repo.get_station_neighbor_track_ids_for_artists = (
            AsyncMock(return_value=[101, 102, 103])
        )
        svc._catalog_repo.get_similar_artist_recommendation_signals = (
            AsyncMock(return_value=([], {}))
        )
        svc._rec_repo.get_track_similarity_candidates_for_artist_ids = (
            AsyncMock(return_value=[])
        )
        svc._rec_repo.get_tracks_by_artist_ids = AsyncMock(return_value=[])
        svc._rec_repo.get_tracks_by_ids = AsyncMock(return_value=[])
        svc._tracks_to_features = AsyncMock(
            return_value=[feat_seed, feat_candidate]
        )

        result = await svc.get_radio(seed_track_id=5, user_id=None)

    assert [t.id for t in result] == [21]
    svc._catalog_repo.get_station_neighbor_track_ids_for_artists.assert_awaited_once_with(
        [900],
        exclude_track_ids=frozenset({5}),
        limit=200,
    )
    assert captured["station_neighbor_track_ids"] == frozenset(
        {101, 102, 103}
    )


def test_interleave_personalized_by_familiarity_avoids_clumping() -> None:
    scored = [
        ScoredTrack(track_id=i, score=1.0 - i * 0.01)
        for i in range(1, 11)
    ]
    listened = {1, 2, 3, 4, 5, 6}

    out = interleave_personalized_by_familiarity(
        scored, listened, target_size=10, novelty_target=0.35
    )

    ids = [s.track_id for s in out]
    assert set(ids) == {i for i in range(1, 11)}
    assert ids[0] in listened
    unseen_positions = [
        idx for idx, tid in enumerate(ids) if tid not in listened
    ]
    assert unseen_positions
    assert unseen_positions[0] <= 3


def test_interleave_personalized_handles_only_unseen() -> None:
    scored = [
        ScoredTrack(track_id=i, score=1.0 - i * 0.01)
        for i in range(1, 6)
    ]
    out = interleave_personalized_by_familiarity(
        scored, set(), target_size=5
    )
    assert [s.track_id for s in out] == [1, 2, 3, 4, 5]


def test_build_radio_queue_no_long_class_run() -> None:
    seed = TrackFeatures(
        track_id=1,
        genre="rock",
        artist_ids=[100],
    )

    def _feat(tid: int, artist: int) -> TrackFeatures:
        return TrackFeatures(
            track_id=tid,
            genre="rock",
            artist_ids=[artist],
            play_count=10,
        )

    familiar_pool = [_feat(tid, 200 + tid) for tid in range(10, 20)]
    unseen_pool = [_feat(tid, 300 + tid) for tid in range(50, 60)]

    queue = build_radio_queue(
        seed,
        listen_history=[],
        candidates=familiar_pool,
        queue_size=12,
        unseen_candidates=unseen_pool,
        liked_track_ids={tid for tid in range(10, 15)},
    )

    assert len(queue) > 0
    classes: list[str] = []
    for row in queue:
        reasons = set(row.reason.split(",")) if row.reason else set()
        if "unseen" in reasons:
            classes.append("unseen")
        elif "like" in reasons or "fav" in reasons:
            classes.append("familiar")
        elif "rediscovery" in reasons:
            classes.append("rediscovery")
        else:
            classes.append("similar")

    run = 1
    for prev, curr in zip(classes, classes[1:], strict=False):
        if prev == curr:
            run += 1
            assert run <= 3, (
                f"freshness-class run too long: {classes}"
            )
        else:
            run = 1


def test_followed_artist_boost_outranks_learned_only() -> None:
    followed = UserPrefs(
        followed_artist_ids=[100],
        preferred_artist_ids=[100, 200],
    )
    learned_only = UserPrefs(
        preferred_artist_ids=[200],
    )

    track_followed = TrackFeatures(
        track_id=1, genre="rock", artist_ids=[100]
    )
    track_learned = TrackFeatures(
        track_id=2, genre="rock", artist_ids=[200]
    )

    scored_followed = score_tracks_for_user(
        followed, [], [track_followed]
    )
    scored_learned = score_tracks_for_user(
        learned_only, [], [track_learned]
    )

    assert scored_followed[0].score > scored_learned[0].score
    assert "follow" in scored_followed[0].reason
    assert "follow" not in scored_learned[0].reason
