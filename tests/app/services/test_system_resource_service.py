from __future__ import annotations

import json
from typing import Any

import pytest

from app.services import system_resource_service as svc

pytestmark = pytest.mark.anyio


class _FakeRedis:
    def __init__(self) -> None:
        self.rows: list[tuple[int, str]] = []

    async def zadd(
        self,
        _key: str,
        mapping: dict[str, int],
    ) -> None:
        for member, score in mapping.items():
            self.rows.append((score, member))

    async def zremrangebyscore(
        self,
        _key: str,
        min_score: int,
        max_score: int,
    ) -> None:
        self.rows = [
            row for row in self.rows if not min_score <= row[0] <= max_score
        ]

    async def zrangebyscore(
        self,
        _key: str,
        min_score: int,
        max_score: int,
    ) -> list[str]:
        return [
            member
            for score, member in self.rows
            if min_score <= score <= max_score
        ]


async def test_system_resource_summary_stores_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = _FakeRedis()
    snapshot: dict[str, Any] = {
        "ts": 1_700_000_000,
        "source": "procfs",
        "cpu_pct": 12.5,
        "load_avg": {"one": 0.1, "five": 0.2, "fifteen": 0.3},
        "memory": {
            "total_bytes": 100,
            "used_bytes": 40,
            "available_bytes": 60,
            "used_pct": 40.0,
        },
        "storage": {
            "path": "/",
            "total_bytes": 200,
            "used_bytes": 50,
            "free_bytes": 150,
            "used_pct": 25.0,
        },
    }

    monkeypatch.setattr(svc, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(svc, "_collect_sync", lambda: snapshot)
    monkeypatch.setattr(svc.time, "time", lambda: 1_700_000_010)

    result = await svc.get_system_resource_summary(minutes=60)

    assert result["current"]["cpu_pct"] == 12.5
    assert result["history"] == [
        {
            "ts": 1_700_000_000,
            "cpu_pct": 12.5,
            "memory_used_pct": 40.0,
            "storage_used_pct": 25.0,
        }
    ]
    stored = json.loads(fake_redis.rows[0][1])
    assert stored["memory_used_pct"] == 40.0
