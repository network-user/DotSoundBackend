from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics_job import LyricsJob
from app.models.track import Track
from app.services import lyrics_cascade as lc

pytestmark = pytest.mark.anyio


async def test_start_cascade_skips_catalog_for_existing_text_sync(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lc,
        "_build_cascade",
        AsyncMock(
            return_value=(
                lc.TIER_CATALOG_ONLY,
                lc.TIER_REMOTE_WHISPER,
            )
        ),
    )
    progress = AsyncMock()
    monkeypatch.setattr(lc, "set_lyrics_progress", progress)

    track = Track(
        title="Need sync",
        artist="Artist",
        file_key="audio/key.mp3",
        is_active=True,
        is_public=True,
        source="internal",
    )
    db_session.add(track)
    await db_session.flush()
    job = LyricsJob(
        id="lj_skip_catalog",
        track_id=track.id,
        progress_id="progress_skip_catalog",
        profile=lc.TIER_CATALOG_ONLY,
        status="queued",
        request_with_sync=True,
    )
    db_session.add(job)
    await db_session.flush()

    active = await lc.start_cascade(
        db_session,
        job=job,
        with_sync=True,
        bypass_cache=False,
        skip_tiers=(lc.TIER_CATALOG_ONLY,),
        skip_reason="existing_text_needs_timing",
    )

    assert active == lc.TIER_REMOTE_WHISPER
    assert job.current_tier == lc.TIER_REMOTE_WHISPER
    assert job.profile == "gpu_full"
    assert job.status == "queued"
    assert job.tier_attempts == [
        {
            "tier": lc.TIER_CATALOG_ONLY,
            "started_at": job.tier_attempts[0]["started_at"],
            "finished_at": job.tier_attempts[0]["finished_at"],
            "status": "skipped",
            "error": "existing_text_needs_timing",
        },
        {
            "tier": lc.TIER_REMOTE_WHISPER,
            "started_at": job.tier_attempts[1]["started_at"],
            "status": "queued",
            "error": None,
        },
    ]
    progress.assert_awaited_once()
