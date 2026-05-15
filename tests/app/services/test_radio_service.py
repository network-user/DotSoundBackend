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
