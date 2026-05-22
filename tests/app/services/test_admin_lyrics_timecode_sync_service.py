from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.admin_lyrics_timecode_sync_service import (
    AdminLyricsTimecodeSyncService,
)


@pytest.mark.anyio
async def test_enqueue_returns_empty_without_targets() -> None:
    session = AsyncMock()
    svc = AdminLyricsTimecodeSyncService(session)
    out = await svc.enqueue(
        MagicMock(id=1),
        track_ids=None,
        enqueue_all_unsynced=False,
        limit=10,
    )
    assert out == {
        "requested": 0,
        "enqueued": 0,
        "skipped": 0,
        "job_ids": [],
    }


@pytest.mark.anyio
async def test_set_priority_requires_value() -> None:
    session = AsyncMock()
    svc = AdminLyricsTimecodeSyncService(session)
    svc._repo.get_align_job = AsyncMock(return_value=MagicMock())
    with pytest.raises(ValueError, match="priority_required"):
        await svc.set_priority(
            "lj_test",
            queue_priority=None,
            bump_next=False,
        )


@pytest.mark.anyio
async def test_set_priority_bump_next_uses_max_plus_one() -> None:
    session = AsyncMock()
    job = MagicMock()
    job.id = "lj_abc"
    job.track_id = 42
    job.pinned_worker_id = None
    job.queue_priority = 0
    job.status = "queued"
    svc = AdminLyricsTimecodeSyncService(session)
    svc._repo.get_align_job = AsyncMock(
        side_effect=[job, job]
    )
    svc._repo.max_queued_align_priority = AsyncMock(
        return_value=7
    )
    svc._repo.track_labels = AsyncMock(
        return_value={42: {"title": "T", "artist": "A"}}
    )
    with patch(
        "app.services.admin_lyrics_timecode_sync_service.AudioComputeAdminService"
    ) as mock_compute_cls:
        mock_compute = mock_compute_cls.return_value
        mock_compute.update_lyrics_job_routing = AsyncMock(
            return_value={"id": "lj_abc"}
        )
        out = await svc.set_priority(
            "lj_abc",
            queue_priority=None,
            bump_next=True,
        )
    mock_compute.update_lyrics_job_routing.assert_awaited_once_with(
        "lj_abc",
        pinned_worker_id=None,
        queue_priority=8,
    )
    assert out["track_id"] == 42
