"""Tests for artist enrichment worker tasks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.repositories.artist import ArtistRepository
from app.services.background_jobs import IdempotencySkipped

pytestmark = pytest.mark.anyio


async def _make_artist(
    session: AsyncSession,
    *,
    name: str = "Test Artist",
    enrichment_status: str = "pending",
    updated_at: datetime | None = None,
) -> Artist:
    repo = ArtistRepository(session)
    artist = await repo.create(
        name=name,
        name_normalized=name.lower(),
        source="soundcloud",
        external_id=None,
    )
    artist.enrichment_status = enrichment_status
    if updated_at is not None:
        artist.updated_at = updated_at
    await session.commit()
    await session.refresh(artist)
    return artist


def _mock_session_ctx(artist_ids: list[int]) -> MagicMock:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = artist_ids

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


async def test_re_enrich_pending_enqueues_stale_artists() -> None:
    from app.services.artist_enrichment_worker import (
        re_enrich_pending_artists_task,
    )

    with patch(
        "app.services.artist_enrichment_worker.AsyncSessionLocal",
        return_value=_mock_session_ctx([10, 20, 30]),
    ), patch(
        "app.services.background_jobs.enqueue",
        new_callable=AsyncMock,
        return_value="bgjob-1",
    ) as mock_enqueue:
        result = await re_enrich_pending_artists_task()

    assert result["enqueued"] == 3
    assert result["skipped"] == 0
    assert result["total_found"] == 3
    assert mock_enqueue.call_count == 3


async def test_re_enrich_pending_no_stale_artists() -> None:
    from app.services.artist_enrichment_worker import (
        re_enrich_pending_artists_task,
    )

    with patch(
        "app.services.artist_enrichment_worker.AsyncSessionLocal",
        return_value=_mock_session_ctx([]),
    ), patch(
        "app.services.background_jobs.enqueue",
        new_callable=AsyncMock,
    ) as mock_enqueue:
        result = await re_enrich_pending_artists_task()

    assert result["enqueued"] == 0
    assert result["total_found"] == 0
    mock_enqueue.assert_not_awaited()


async def test_re_enrich_pending_idempotency_skipped_counted_as_skipped() -> (
    None
):
    from app.services.artist_enrichment_worker import (
        re_enrich_pending_artists_task,
    )

    with patch(
                    "app.services.artist_enrichment_worker.AsyncSessionLocal",
                    return_value=_mock_session_ctx([11, 22]),
                ), patch(
                    "app.services.background_jobs.enqueue",
                    new_callable=AsyncMock,
                    side_effect=[IdempotencySkipped("artist-enrich:11"), "bgjob-2"],
                ):
        result = await re_enrich_pending_artists_task()

    assert result["enqueued"] == 1
    assert result["skipped"] == 1
    assert result["total_found"] == 2


async def test_re_enrich_pending_uses_idempotency_key() -> None:
    from app.services.artist_enrichment_worker import (
        re_enrich_pending_artists_task,
    )

    captured_calls: list[dict] = []

    async def _capture_enqueue(task, *, payload, idempotency_key, **kw):
        captured_calls.append(
            {"payload": payload, "idempotency_key": idempotency_key}
        )
        return "bgjob-x"

    with patch(
        "app.services.artist_enrichment_worker.AsyncSessionLocal",
        return_value=_mock_session_ctx([99]),
    ), patch(
        "app.services.background_jobs.enqueue",
        side_effect=_capture_enqueue,
    ):
        await re_enrich_pending_artists_task()

    assert len(captured_calls) == 1
    assert captured_calls[0]["idempotency_key"] == "artist-enrich:99"
    assert captured_calls[0]["payload"] == {"artist_id": 99}
