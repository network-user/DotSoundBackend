from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services import radio_auto_skip_stats_service as svc

pytestmark = pytest.mark.anyio


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, str, int] | tuple[str, int]] = []

    def hincrby(self, key: str, field: str, amount: int) -> FakePipeline:
        self._ops.append((key, field, amount))
        return self

    def expire(self, key: str, seconds: int) -> FakePipeline:
        self._ops.append((key, seconds))
        return self

    async def execute(self) -> None:
        for op in self._ops:
            if len(op) != 3:
                continue
            key, field, amount = op
            bucket = self._redis.hashes.setdefault(key, {})
            bucket[field] = bucket.get(field, 0) + amount


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, int]] = {}

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    async def hgetall(self, key: str) -> dict[str, str]:
        return {
            field: str(value)
            for field, value in self.hashes.get(key, {}).items()
        }


async def test_radio_auto_skip_stats_aggregates_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(svc, "get_redis_client", lambda: redis)
    now = datetime(2026, 5, 16, tzinfo=UTC)

    await svc.record_radio_auto_skip_reason(
        error_code="soundcloud_stream_unavailable",
        error_reason="provider_manifest_not_found_for_all_formats",
        now=now,
    )
    await svc.record_radio_auto_skip_reason(
        error_code="soundcloud_stream_unavailable",
        error_reason="provider_manifest_not_found_for_all_formats",
        now=now,
    )
    await svc.record_radio_auto_skip_reason(
        error_code=None,
        error_reason=None,
        now=now,
    )

    rows = await svc.get_radio_auto_skip_reason_stats(
        days=1,
        limit=10,
        now=now,
    )

    assert rows == [
        {
            "error_code": "soundcloud_stream_unavailable",
            "error_reason": (
                "provider_manifest_not_found_for_all_formats"
            ),
            "count": 2,
        },
        {
            "error_code": "unknown",
            "error_reason": "unknown",
            "count": 1,
        },
    ]
