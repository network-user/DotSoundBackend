from __future__ import annotations

from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest

from dotsound_private_core.services.abuse import (
    TOR_REDIS_KEY,
)

from app.core.tor_checker import (
    is_tor_exit_node,
    refresh_tor_exit_nodes,
)

pytestmark = pytest.mark.anyio


def _fake_settings() -> MagicMock:
    s = MagicMock()
    s.redis_url = "redis://localhost:6379/0"
    return s


class TestRefreshTorExitNodes:
    async def test_fetches_and_stores_ips(
        self,
    ) -> None:
        body = "1.2.3.4\n5.6.7.8\n# comment\n"
        resp = MagicMock()
        resp.text = body
        resp.raise_for_status = MagicMock()

        http_client = AsyncMock()
        http_client.get = AsyncMock(
            return_value=resp
        )
        http_client.__aenter__ = AsyncMock(
            return_value=http_client
        )
        http_client.__aexit__ = AsyncMock()

        pipe = MagicMock()
        pipe.delete = MagicMock(return_value=pipe)
        pipe.sadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock()

        redis = MagicMock()
        redis.pipeline = MagicMock(
            return_value=pipe
        )
        redis.aclose = AsyncMock()

        with (
            patch(
                "app.core.tor_checker.settings",
                _fake_settings(),
            ),
            patch(
                "httpx.AsyncClient",
                return_value=http_client,
            ),
            patch(
                "redis.asyncio.from_url",
                return_value=redis,
            ),
        ):
            count = await refresh_tor_exit_nodes()

        assert count == 2
        pipe.sadd.assert_any_call(
            TOR_REDIS_KEY, "1.2.3.4"
        )
        pipe.sadd.assert_any_call(
            TOR_REDIS_KEY, "5.6.7.8"
        )

    async def test_http_failure_returns_zero(
        self,
    ) -> None:
        resp = MagicMock()
        resp.raise_for_status = MagicMock(
            side_effect=Exception("HTTP 500")
        )

        http_client = AsyncMock()
        http_client.get = AsyncMock(
            return_value=resp
        )
        http_client.__aenter__ = AsyncMock(
            return_value=http_client
        )
        http_client.__aexit__ = AsyncMock(
            return_value=False
        )

        with (
            patch(
                "app.core.tor_checker.settings",
                _fake_settings(),
            ),
            patch(
                "httpx.AsyncClient",
                return_value=http_client,
            ),
        ):
            count = await refresh_tor_exit_nodes()

        assert count == 0

    async def test_empty_list_returns_zero(
        self,
    ) -> None:
        resp = MagicMock()
        resp.text = "# only comments\n"
        resp.raise_for_status = MagicMock()

        http_client = AsyncMock()
        http_client.get = AsyncMock(
            return_value=resp
        )
        http_client.__aenter__ = AsyncMock(
            return_value=http_client
        )
        http_client.__aexit__ = AsyncMock()

        with (
            patch(
                "app.core.tor_checker.settings",
                _fake_settings(),
            ),
            patch(
                "httpx.AsyncClient",
                return_value=http_client,
            ),
        ):
            count = await refresh_tor_exit_nodes()

        assert count == 0


class TestIsTorExitNode:
    async def test_known_tor_ip_returns_true(
        self,
    ) -> None:
        redis = AsyncMock()
        redis.sismember = AsyncMock(return_value=1)
        redis.aclose = AsyncMock()

        with (
            patch(
                "app.core.tor_checker.settings",
                _fake_settings(),
            ),
            patch(
                "redis.asyncio.from_url",
                return_value=redis,
            ),
        ):
            result = await is_tor_exit_node("1.2.3.4")

        assert result is True
        redis.sismember.assert_awaited_once_with(
            TOR_REDIS_KEY, "1.2.3.4"
        )

    async def test_normal_ip_returns_false(
        self,
    ) -> None:
        redis = AsyncMock()
        redis.sismember = AsyncMock(return_value=0)
        redis.aclose = AsyncMock()

        with (
            patch(
                "app.core.tor_checker.settings",
                _fake_settings(),
            ),
            patch(
                "redis.asyncio.from_url",
                return_value=redis,
            ),
        ):
            result = await is_tor_exit_node("9.9.9.9")

        assert result is False
