"""Tests for Elasticsearch client wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.search.es_client as mod


@pytest.mark.anyio
async def test_close_es_clears_singleton() -> None:
    with patch.object(mod, "_es_configured", return_value=True), patch(
        "app.search.es_client.AsyncElasticsearch"
    ) as es_cls:
        inst = MagicMock()
        inst.close = AsyncMock()
        es_cls.return_value = inst
        mod.get_es()
        assert mod._client is not None
        await mod.close_es()
        inst.close.assert_awaited()
        assert mod._client is None


def test_get_es_when_not_configured() -> None:
    with (
        patch.object(
            mod,
            "_es_configured",
            return_value=False,
        ),
    ):
        with pytest.raises(
            RuntimeError, match="Elasticsearch is not configured"
        ):
            mod.get_es()
