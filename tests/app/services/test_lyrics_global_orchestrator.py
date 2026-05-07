"""Offline tests for the global post-import lyrics orchestrator.

The orchestrator's main loop is fire-and-forget at worker startup;
these tests cover the pure helpers and the per-item processing
path so we can verify pacing decisions (skipped / blocked /
normal) without standing up Redis or Taskiq.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import lyrics_global_orchestrator as lgo_mod
from app.services.lyrics_global_orchestrator import (
    _deserialize,
    _is_block_signal,
    _process_one,
    _QueueItem,
    _serialize,
    enqueue,
    stop_orchestrator_task,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.lyrics_global_orchestrator"


def test_serialize_deserialize_roundtrip() -> None:
    item = _QueueItem(track_id=42, with_sync=True)
    raw = _serialize(item)
    parsed = _deserialize(raw)
    assert parsed == item


def test_deserialize_invalid_returns_none() -> None:
    assert _deserialize("not-json") is None
    assert _deserialize('{"foo": 1}') is None


def test_is_block_signal_matches_known_markers() -> None:
    assert _is_block_signal("captcha returned 429") is True
    assert _is_block_signal("proxy pool_exhaust") is True
    assert _is_block_signal("Pool Exhausted") is True
    assert _is_block_signal("EXHAUSTED") is True
    assert _is_block_signal("normal traffic") is False
    assert _is_block_signal(None) is False
    assert _is_block_signal("") is False


@patch(f"{_MOD}.get_redis_client")
async def test_enqueue_pushes_serialized_item(
    mock_redis_client: MagicMock,
) -> None:
    redis = AsyncMock()
    mock_redis_client.return_value = redis

    await enqueue(123, with_sync=True)

    redis.rpush.assert_awaited_once()
    args = redis.rpush.await_args.args
    payload = _deserialize(args[1])
    assert payload == _QueueItem(track_id=123, with_sync=True)


def _svc_enqueue_mock(ret: str | None) -> MagicMock:
    inst = MagicMock()
    inst.enqueue_background_lyrics = AsyncMock(return_value=ret)
    return inst


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_service.LyricsService",
)
async def test_process_one_skipped_when_enqueue_returns_none(
    mock_svc_cls: MagicMock,
    _mock_err: MagicMock,
) -> None:
    mock_svc_cls.return_value = _svc_enqueue_mock(None)

    with patch(
        "app.repositories.lyrics.LyricsRepository.get_by_track_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        tag = await _process_one(_QueueItem(track_id=7, with_sync=True))

    assert tag == "skipped"


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_service.LyricsService",
)
async def test_process_one_skips_when_lyrics_plain_text_exists(
    mock_svc_cls: MagicMock,
    _mock_err: MagicMock,
) -> None:
    fake_existing = MagicMock()
    fake_existing.plain_text = "hello"
    with patch(
        "app.repositories.lyrics.LyricsRepository.get_by_track_id",
        new_callable=AsyncMock,
        return_value=fake_existing,
    ):
        tag = await _process_one(_QueueItem(track_id=11, with_sync=True))

    assert tag == "skipped"
    mock_svc_cls.assert_not_called()


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_service.LyricsService",
)
async def test_process_one_returns_normal_after_enqueue(
    mock_svc_cls: MagicMock,
    _mock_err: MagicMock,
) -> None:
    mock_svc_cls.return_value = _svc_enqueue_mock("p1")

    with patch(
        "app.repositories.lyrics.LyricsRepository.get_by_track_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        tag = await _process_one(_QueueItem(track_id=11, with_sync=False))

    assert tag == "normal"
    mock_svc_cls.return_value.enqueue_background_lyrics.assert_awaited()


@patch(
    f"{_MOD}._peek_last_error",
    return_value="captcha challenged",
)
@patch(
    "app.services.lyrics_service.LyricsService",
)
async def test_process_one_flags_block_signal(
    mock_svc_cls: MagicMock,
    _mock_err: MagicMock,
) -> None:
    mock_svc_cls.return_value = _svc_enqueue_mock("p1")

    with patch(
        "app.repositories.lyrics.LyricsRepository.get_by_track_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        tag = await _process_one(_QueueItem(track_id=99, with_sync=True))

    assert tag == "blocked"


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_service.LyricsService",
)
async def test_process_one_returns_error_on_enqueue_failure(
    mock_svc_cls: MagicMock,
    _mock_err: MagicMock,
) -> None:
    inst = MagicMock()
    inst.enqueue_background_lyrics = AsyncMock(
        side_effect=RuntimeError("broker down"),
    )
    mock_svc_cls.return_value = inst

    with patch(
        "app.repositories.lyrics.LyricsRepository.get_by_track_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        tag = await _process_one(_QueueItem(track_id=77, with_sync=True))

    assert tag == "error"


async def test_stop_orchestrator_noop_when_no_task() -> None:
    lgo_mod._orchestrator_task = None
    await stop_orchestrator_task()
    assert lgo_mod._orchestrator_task is None


async def test_stop_orchestrator_noop_when_task_done() -> None:
    async def done_coro() -> None:
        return

    t = asyncio.create_task(done_coro())
    await t
    lgo_mod._orchestrator_task = t
    await stop_orchestrator_task()
    assert lgo_mod._orchestrator_task is None


async def test_stop_orchestrator_cancels_pending_and_clears() -> None:
    async def long_sleep() -> None:
        try:
            await asyncio.sleep(3600.0)
        except asyncio.CancelledError:
            raise

    t = asyncio.create_task(long_sleep())
    lgo_mod._orchestrator_task = t
    await stop_orchestrator_task()
    assert lgo_mod._orchestrator_task is None
    assert t.done()
    assert t.cancelled()
