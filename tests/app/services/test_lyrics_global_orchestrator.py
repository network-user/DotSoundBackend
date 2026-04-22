"""Offline tests for the global post-import lyrics orchestrator.

The orchestrator's main loop is fire-and-forget at worker startup;
these tests cover the pure helpers and the per-item processing
path so we can verify pacing decisions (skipped / blocked /
normal) without standing up Redis or Taskiq.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lyrics_global_orchestrator import (
    _deserialize,
    _is_block_signal,
    _process_one,
    _QueueItem,
    _serialize,
    enqueue,
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


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_worker.generate_lyrics_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.get_redis_client")
async def test_process_one_returns_skipped_when_lock_held(
    mock_redis_client: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
) -> None:
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=1)
    mock_redis_client.return_value = redis

    tag = await _process_one(_QueueItem(track_id=7, with_sync=True))

    assert tag == "skipped"
    mock_kiq.assert_not_awaited()


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_worker.generate_lyrics_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.get_redis_client")
async def test_process_one_returns_normal_after_kiq(
    mock_redis_client: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
) -> None:
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    mock_redis_client.return_value = redis

    tag = await _process_one(_QueueItem(track_id=11, with_sync=False))

    assert tag == "normal"
    mock_kiq.assert_awaited_once_with(11, with_sync=False, progress_id="")


@patch(
    f"{_MOD}._peek_last_error",
    return_value="captcha challenged",
)
@patch(
    "app.services.lyrics_worker.generate_lyrics_task.kiq",
    new_callable=AsyncMock,
)
@patch(f"{_MOD}.get_redis_client")
async def test_process_one_flags_block_signal(
    mock_redis_client: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
) -> None:
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    mock_redis_client.return_value = redis

    tag = await _process_one(_QueueItem(track_id=99, with_sync=True))

    assert tag == "blocked"
    mock_kiq.assert_awaited_once()


@patch(f"{_MOD}._peek_last_error", return_value=None)
@patch(
    "app.services.lyrics_worker.generate_lyrics_task.kiq",
    new_callable=AsyncMock,
    side_effect=RuntimeError("broker down"),
)
@patch(f"{_MOD}.get_redis_client")
async def test_process_one_returns_error_on_kiq_failure(
    mock_redis_client: MagicMock,
    mock_kiq: AsyncMock,
    _mock_err: MagicMock,
) -> None:
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    mock_redis_client.return_value = redis

    tag = await _process_one(_QueueItem(track_id=77, with_sync=True))

    assert tag == "error"
