"""Offline tests for the post-import lyrics orchestrator.

All external dependencies (Taskiq ``.kiq``, PrivateCore proxy pool,
wall-clock sleep, RNG) are patched so the whole test suite runs
synchronously and never touches the network. Every assertion is
about how the orchestrator *chooses* to sequence work — not about
the downstream lyrics worker itself.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.user import User

pytestmark = pytest.mark.anyio

_MOD = "app.services.import_lyrics_worker"


async def _make_user(
    session: AsyncSession, telegram_id: int = 9100
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_track(
    session: AsyncSession,
    uploader_id: int,
    title: str = "T",
    artist: str = "A",
) -> Track:
    track = Track(
        title=title,
        artist=artist,
        uploaded_by_id=uploader_id,
        is_active=True,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


async def _make_job_with_tracks(
    session: AsyncSession,
    user_id: int,
    track_ids: list[int],
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source="yandex_music",
        status="done",
        tracks_data={
            "imported": [
                {"track_id": tid, "status": "done"}
                for tid in track_ids
            ]
        },
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


def _session_ctx(session: AsyncSession) -> AsyncMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(f"{_MOD}.generate_lyrics_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_skips_tracks_with_existing_lyrics(
    mock_session_local: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
    _mock_sleep: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=9101)
    t1 = await _make_track(session, user.id, title="one")
    t2 = await _make_track(session, user.id, title="two")
    t3 = await _make_track(session, user.id, title="three")
    # Track t2 already has lyrics — must be skipped.
    session.add(
        TrackLyrics(
            track_id=t2.id,
            plain_text="already saved",
            source="manual",
        )
    )
    await session.flush()

    job = await _make_job_with_tracks(
        session, user.id, [t1.id, t2.id, t3.id]
    )
    await session.commit()
    mock_session_local.return_value = _session_ctx(session)

    from app.services.import_lyrics_worker import (
        process_import_lyrics_task,
    )

    await process_import_lyrics_task(job.id)

    kiq_track_ids = sorted(
        call.args[0] for call in mock_kiq.call_args_list
    )
    assert kiq_track_ids == sorted([t1.id, t3.id])
    for call in mock_kiq.call_args_list:
        assert call.kwargs.get("with_sync") is True


@patch(f"{_MOD}.random.uniform", return_value=17.0)
@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(f"{_MOD}.generate_lyrics_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_pacing_between_tracks_uses_uniform_delay(
    mock_session_local: MagicMock,
    _mock_kiq: AsyncMock,
    _mock_err: MagicMock,
    mock_sleep: AsyncMock,
    mock_uniform: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=9102)
    tracks = [
        await _make_track(session, user.id, title=f"t{i}")
        for i in range(3)
    ]
    job = await _make_job_with_tracks(
        session, user.id, [t.id for t in tracks]
    )
    await session.commit()
    mock_session_local.return_value = _session_ctx(session)

    from app.services.import_lyrics_worker import (
        process_import_lyrics_task,
    )

    await process_import_lyrics_task(job.id)

    # No sleep after the last track → exactly N-1 sleeps.
    assert mock_sleep.await_count == len(tracks) - 1
    for call in mock_sleep.await_args_list:
        assert call.args == (17.0,)
    # random.uniform called with the configured delay bounds.
    assert mock_uniform.call_count >= len(tracks) - 1
    lo, hi = mock_uniform.call_args_list[0].args
    assert lo < hi
    assert lo > 0


@patch(f"{_MOD}.random.uniform", return_value=17.0)
@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(f"{_MOD}._peek_last_error")
@patch(f"{_MOD}.generate_lyrics_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_cooldown_applied_after_block_signal(
    mock_session_local: MagicMock,
    _mock_kiq: AsyncMock,
    mock_err: MagicMock,
    mock_sleep: AsyncMock,
    _mock_uniform: MagicMock,
    session: AsyncSession,
) -> None:
    # Two tracks, second iteration sees a captcha signal from the
    # proxy pool → the sleep taken before track 3 must be the
    # cooldown value, not a uniform sample.
    user = await _make_user(session, telegram_id=9103)
    tracks = [
        await _make_track(session, user.id, title=f"t{i}")
        for i in range(3)
    ]
    job = await _make_job_with_tracks(
        session, user.id, [t.id for t in tracks]
    )
    await session.commit()
    mock_session_local.return_value = _session_ctx(session)

    # Error signal sequence matches per-track inspection order:
    # after track 1 — clean, after track 2 — block, after track 3 —
    # irrelevant (no sleep on last track).
    mock_err.side_effect = [
        None,
        "captcha_required: showcaptcha redirect",
        None,
    ]

    from app.config import settings
    from app.services.import_lyrics_worker import (
        process_import_lyrics_task,
    )

    await process_import_lyrics_task(job.id)

    # Two sleeps total: one after track 1 (clean → uniform=17),
    # one after track 2 (block → cooldown).
    assert mock_sleep.await_count == 2
    first_sleep = mock_sleep.await_args_list[0].args[0]
    second_sleep = mock_sleep.await_args_list[1].args[0]
    assert first_sleep == 17.0
    assert second_sleep == float(
        settings.yandex_music_import_lyrics_cooldown_seconds
    )


@patch(f"{_MOD}.random.uniform", return_value=1.0)
@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(
    f"{_MOD}._peek_last_error",
    return_value="captcha: showcaptcha redirect",
)
@patch(f"{_MOD}.generate_lyrics_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_early_exit_after_max_consecutive_blocks(
    mock_session_local: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
    _mock_sleep: AsyncMock,
    _mock_uniform: MagicMock,
    session: AsyncSession,
) -> None:
    # Every track trips the block signal. After MAX_CONSECUTIVE_BLOCKS
    # (=5) hits in a row the orchestrator must bail out without
    # enqueueing the remaining tracks.
    from app.services.import_lyrics_worker import (
        MAX_CONSECUTIVE_BLOCKS,
        process_import_lyrics_task,
    )

    total = MAX_CONSECUTIVE_BLOCKS + 2  # two extras beyond the limit
    user = await _make_user(session, telegram_id=9104)
    tracks = [
        await _make_track(session, user.id, title=f"t{i}")
        for i in range(total)
    ]
    job = await _make_job_with_tracks(
        session, user.id, [t.id for t in tracks]
    )
    await session.commit()
    mock_session_local.return_value = _session_ctx(session)

    await process_import_lyrics_task(job.id)

    assert mock_kiq.await_count == MAX_CONSECUTIVE_BLOCKS


@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(f"{_MOD}.generate_lyrics_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_no_imported_tracks_is_noop(
    mock_session_local: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
    mock_sleep: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=9105)
    job = await _make_job_with_tracks(session, user.id, [])
    await session.commit()
    mock_session_local.return_value = _session_ctx(session)

    from app.services.import_lyrics_worker import (
        process_import_lyrics_task,
    )

    await process_import_lyrics_task(job.id)

    assert mock_kiq.await_count == 0
    assert mock_sleep.await_count == 0


@patch(f"{_MOD}.asyncio.sleep", new_callable=AsyncMock)
@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(f"{_MOD}.generate_lyrics_task.kiq", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_missing_job_is_noop(
    mock_session_local: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
    mock_sleep: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_session_local.return_value = _session_ctx(session)

    from app.services.import_lyrics_worker import (
        process_import_lyrics_task,
    )

    await process_import_lyrics_task(999_999)

    assert mock_kiq.await_count == 0
    assert mock_sleep.await_count == 0
