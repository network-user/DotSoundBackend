from __future__ import annotations

import pytest

from app.services import sc_dead_track_cache as dead_cache

pytestmark = pytest.mark.anyio


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, tuple[bytes, int]] = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def set(
        self,
        key: str,
        value: str | bytes,
        *,
        ex: int | None = None,
    ) -> bool:
        if isinstance(value, str):
            value = value.encode()
        self.store[key] = (value, ex or 0)
        return True

    async def delete(self, key: str) -> int:
        existed = 1 if key in self.store else 0
        self.store.pop(key, None)
        return existed

    async def scan(
        self,
        cursor: int = 0,
        *,
        match: str | None = None,
        count: int = 100,
    ) -> tuple[int, list[bytes]]:
        prefix = (match or "").rstrip("*")
        matched = [
            k.encode() for k in self.store if k.startswith(prefix)
        ]
        return 0, matched


class _ExplodingRedis:
    async def exists(self, _key: str) -> int:
        raise RuntimeError("redis down")

    async def set(
        self, *_args: object, **_kwargs: object
    ) -> bool:
        raise RuntimeError("redis down")

    async def delete(self, _key: str) -> int:
        raise RuntimeError("redis down")

    async def scan(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> tuple[int, list[bytes]]:
        raise RuntimeError("redis down")


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr(
        dead_cache, "get_redis_client", lambda: fake
    )
    return fake


async def test_mark_then_is_dead(fake_redis: _FakeRedis) -> None:
    assert await dead_cache.is_dead(2059350776) is False
    await dead_cache.mark_dead(2059350776, reason="http_404")
    assert await dead_cache.is_dead(2059350776) is True
    assert any(
        b"http_404" in v[0] for v in fake_redis.store.values()
    )


async def test_mark_dead_respects_explicit_ttl(
    fake_redis: _FakeRedis,
) -> None:
    await dead_cache.mark_dead(
        "track-x", reason="gone", ttl_seconds=42
    )
    assert any(v[1] == 42 for v in fake_redis.store.values())


async def test_clear_removes_dead_marker(
    fake_redis: _FakeRedis,
) -> None:
    await dead_cache.mark_dead(99)
    assert await dead_cache.is_dead(99) is True
    await dead_cache.clear(99)
    assert await dead_cache.is_dead(99) is False


async def test_count_dead_uses_scan(
    fake_redis: _FakeRedis,
) -> None:
    await dead_cache.mark_dead(1)
    await dead_cache.mark_dead(2)
    await dead_cache.mark_dead("abc")
    assert await dead_cache.count_dead() == 3


async def test_is_dead_graceful_on_redis_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dead_cache, "get_redis_client", lambda: _ExplodingRedis()
    )
    assert await dead_cache.is_dead(1) is False


async def test_count_dead_returns_sentinel_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dead_cache, "get_redis_client", lambda: _ExplodingRedis()
    )
    assert await dead_cache.count_dead() == -1


async def test_mark_dead_swallows_write_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dead_cache, "get_redis_client", lambda: _ExplodingRedis()
    )
    await dead_cache.mark_dead(1, reason="t")
