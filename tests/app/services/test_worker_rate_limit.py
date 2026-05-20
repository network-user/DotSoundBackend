from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import worker_rate_limit as rl

pytestmark = pytest.mark.anyio


class _CountingRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expire = AsyncMock()

    async def incr(self, key: str) -> int:
        value = self.counts.get(key, 0) + 1
        self.counts[key] = value
        return value


async def test_audio_download_limit_allows_asr_burst(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = _CountingRedis()
    monkeypatch.setattr(
        rl,
        "get_redis_client",
        MagicMock(return_value=redis),
    )

    for _ in range(11):
        await rl.check_and_consume(
            db_session,
            worker_id="w_audio_burst",
            action="audio",
        )


async def test_failure_reporting_limit_allows_retry_burst(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = _CountingRedis()
    monkeypatch.setattr(
        rl,
        "get_redis_client",
        MagicMock(return_value=redis),
    )

    for _ in range(31):
        await rl.check_and_consume(
            db_session,
            worker_id="w_fail_burst",
            action="fail",
        )
