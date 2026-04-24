from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services import search_query_service


@pytest.mark.anyio
async def test_es_search_tracks_returns_none_when_not_configured() -> None:
    with patch(
        "app.services.search_query_service.es_available",
        return_value=False,
    ):
        out = await search_query_service.es_search_tracks(
            "x", page=1, size=10, playable_only=False
        )
    assert out is None


@pytest.mark.anyio
async def test_es_suggest_mixed_empty_query() -> None:
    with patch(
        "app.services.search_query_service.es_available",
        return_value=True,
    ):
        out = await search_query_service.es_suggest_mixed("  ", limit=4)
    assert out is None


@pytest.mark.anyio
async def test_es_search_tracks_parses_ids() -> None:
    mock_es = AsyncMock()
    mock_es.search = AsyncMock(
        return_value={
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "7",
                        "_source": {"track_id": 7},
                    }
                ],
            }
        }
    )
    with (
        patch(
            "app.services.search_query_service.es_available",
            return_value=True,
        ),
        patch(
            "app.services.search_query_service.get_es",
            return_value=mock_es,
        ),
    ):
        out = await search_query_service.es_search_tracks(
            "hello", page=1, size=10, playable_only=False
        )
    assert out is not None
    ids, total = out
    assert total == 1
    assert ids == [7]
