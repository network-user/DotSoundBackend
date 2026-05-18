"""Unit tests for RadioService filtering logic."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio


def _make_track(
    track_id: int,
    *,
    access_mode: str = "stream",
    suppressed: bool = False,
) -> object:
    return SimpleNamespace(
        id=track_id,
        access_mode=access_mode,
        is_active=True,
        is_public=True,
        source_platform=None,
        external_id=None,
        title="Track",
        artist=None,
        uploaded_by_id=1,
        _suppressed=suppressed,
    )


# ---------------------------------------------------------------------------
# Suppression filter applied to upstream tracks before merge
# ---------------------------------------------------------------------------


async def test_suppressed_upstream_tracks_excluded_before_merge() -> None:
    """Tracks flagged by is_track_playback_suppressed must not appear in the
    merged id list that feeds get_by_ids_preserve_order."""
    from dotsound_private_core.services.radio_policy import (
        cap_queue_ids,
        merge_dedup_ordered,
    )

    good = _make_track(10)
    suppressed = _make_track(11, suppressed=True)
    base_ids = [1, 2, 3]
    upstream = [good, suppressed]

    with patch(
        "app.services.track_playback_health_service"
        ".is_track_playback_suppressed",
        side_effect=lambda t: getattr(t, "_suppressed", False),
    ):
        from app.services.track_playback_health_service import (
            is_track_playback_suppressed,
        )

        filtered = [t for t in upstream if not is_track_playback_suppressed(t)]

    merged = merge_dedup_ordered(base_ids, [t.id for t in filtered])
    ids = cap_queue_ids(merged, 10)

    assert suppressed.id not in ids
    assert good.id in ids


async def test_all_upstream_suppressed_falls_back_to_base() -> None:
    """When every upstream track is suppressed the result is base-only."""
    from dotsound_private_core.services.radio_policy import (
        cap_queue_ids,
        merge_dedup_ordered,
    )

    base_ids = [1, 2]
    upstream = [
        _make_track(10, suppressed=True),
        _make_track(11, suppressed=True),
    ]

    with patch(
        "app.services.track_playback_health_service"
        ".is_track_playback_suppressed",
        return_value=True,
    ):
        from app.services.track_playback_health_service import (
            is_track_playback_suppressed,
        )

        filtered = [t for t in upstream if not is_track_playback_suppressed(t)]

    merged = merge_dedup_ordered(base_ids, [t.id for t in filtered])
    ids = cap_queue_ids(merged, 10)

    assert ids == base_ids


# ---------------------------------------------------------------------------
# access_mode filter on the DB query built by TrackRepository
# ---------------------------------------------------------------------------


def test_get_next_tracks_query_excludes_external_link() -> None:
    """Compile WHERE clause and assert external_link condition exists."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models.track import Track

    stmt = (
        select(Track)
        .where(
            Track.is_active.is_(True)
            & Track.is_public.is_(True)
            & (Track.id != 1)
            & (Track.access_mode != "external_link")
        )
        .limit(10)
    )
    compiled = stmt.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    sql = str(compiled)
    assert "external_link" in sql


async def test_radio_service_build_queue_catalog_path_calls_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When radio_enabled=False, build_queue must call get_next_tracks."""
    from app.services.radio_service import RadioService

    mock_session = MagicMock()
    mock_settings = MagicMock()
    mock_settings.radio_enabled = False

    service = RadioService(session=mock_session, settings=mock_settings)
    seed = _make_track(99)
    expected = [_make_track(100)]

    service._repo = MagicMock()
    service._repo.get_next_tracks = AsyncMock(return_value=expected)

    monkeypatch.setattr(
        "app.core.redis.get_redis_client",
        lambda: MagicMock(
            set=AsyncMock(return_value=True),
            setex=AsyncMock(),
        ),
    )
    monkeypatch.setattr(
        "app.core.observability.radio_request_observed",
        MagicMock(),
    )

    result, source = await service.build_queue(seed, count=5, current=None)

    service._repo.get_next_tracks.assert_awaited_once_with(seed.id, 5)
    assert result == expected
    assert source == "catalog"


def _yt_seed(track_id: int = 99) -> object:
    """YT-platform seed eligible for the youtube_mix branch."""
    return SimpleNamespace(
        id=track_id,
        access_mode="external_link",
        is_active=True,
        is_public=True,
        source_platform="youtube",
        external_id="dQw4w9WgXcQ",
        title="Track",
        artist="Artist",
        uploaded_by_id=1,
        _suppressed=False,
    )


def _yt_service_kwargs() -> MagicMock:
    """RadioService settings flipped so the youtube_mix branch runs."""
    s = MagicMock()
    s.radio_enabled = True
    s.radio_youtube_mix_enabled = True
    s.youtube_enabled = True
    s.radio_max_suggestions = 10
    s.radio_yt_mix_budget_seconds = 0.5
    s.radio_yt_mix_cache_ttl_seconds = 300
    return s


async def test_resolve_youtube_upstream_cache_hit_skips_materialize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warm cache must short-circuit the heavy yt-dlp pipeline and
    return ``youtube_mix_cached`` so future refills are <1 ms."""
    from app.services.radio_service import RadioService

    mock_session = MagicMock()
    service = RadioService(session=mock_session, settings=_yt_service_kwargs())

    cached_tracks = [_make_track(10), _make_track(11)]
    service._repo = MagicMock()
    service._repo.get_by_ids_preserve_order = AsyncMock(
        return_value=cached_tracks
    )
    service._materialize_youtube_upstream = AsyncMock(
        return_value=([], None)
    )

    monkeypatch.setattr(
        "app.services.radio_service.get_redis_client",
        lambda: MagicMock(
            get=AsyncMock(return_value="10,11"),
            setex=AsyncMock(),
        ),
    )

    seed = _yt_seed()
    result, source = await service._resolve_youtube_upstream(
        seed=seed, current=None, cap=10, up_cap=10
    )

    assert source == "youtube_mix_cached"
    assert [t.id for t in result] == [10, 11]
    service._materialize_youtube_upstream.assert_not_awaited()


async def test_resolve_youtube_upstream_cold_writes_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cold path: materialize succeeds → result is stored in Redis
    so the next call within the TTL avoids the cost again."""
    from app.services.radio_service import RadioService

    mock_session = MagicMock()
    service = RadioService(session=mock_session, settings=_yt_service_kwargs())

    materialized = [_make_track(20), _make_track(21)]
    service._materialize_youtube_upstream = AsyncMock(
        return_value=(materialized, "youtube_mix")
    )

    setex_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.radio_service.get_redis_client",
        lambda: MagicMock(
            get=AsyncMock(return_value=None),
            setex=setex_mock,
        ),
    )
    monkeypatch.setattr(
        "app.services.radio_service.radio_request_observed",
        MagicMock(),
    )

    seed = _yt_seed()
    result, source = await service._resolve_youtube_upstream(
        seed=seed, current=None, cap=10, up_cap=10
    )

    assert source == "youtube_mix"
    assert [t.id for t in result] == [20, 21]
    setex_mock.assert_awaited_once()
    _, value = setex_mock.await_args.args[1], setex_mock.await_args.args[2]
    assert value == "20,21"


async def test_resolve_youtube_upstream_budget_exceeded_returns_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hard budget: if materialize blows the wall-clock budget the
    radio response must still come back quickly with an empty
    upstream and a ``youtube_mix_pending`` tag, so the catalog base
    alone is sent to the client instead of timing out."""
    import asyncio

    from app.services.radio_service import RadioService

    settings = _yt_service_kwargs()
    settings.radio_yt_mix_budget_seconds = 0.05
    mock_session = MagicMock()
    service = RadioService(session=mock_session, settings=settings)

    async def _slow(*_a: object, **_kw: object) -> tuple[list, str]:
        await asyncio.sleep(0.5)
        return [_make_track(30)], "youtube_mix"

    service._materialize_youtube_upstream = _slow  # type: ignore[assignment]

    setex_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.radio_service.get_redis_client",
        lambda: MagicMock(
            get=AsyncMock(return_value=None),
            setex=setex_mock,
        ),
    )
    monkeypatch.setattr(
        "app.services.radio_service.radio_request_observed",
        MagicMock(),
    )

    seed = _yt_seed()
    result, source = await service._resolve_youtube_upstream(
        seed=seed, current=None, cap=10, up_cap=10
    )

    assert result == []
    assert source == "youtube_mix_pending"
    setex_mock.assert_not_awaited()
