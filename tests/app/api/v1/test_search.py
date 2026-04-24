"""API tests for /search routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.search_query_service import SuggestItem

pytestmark = pytest.mark.anyio


def _mock_settings(
    **kwargs: str | bool,
) -> MagicMock:
    s = MagicMock()
    s.elasticsearch_enabled = kwargs.get("elasticsearch_enabled", True)
    s.elasticsearch_url = kwargs.get("elasticsearch_url", "")
    s.elasticsearch_index_tracks = kwargs.get(
        "elasticsearch_index_tracks", "t"
    )
    s.elasticsearch_index_artists = kwargs.get(
        "elasticsearch_index_artists", "a"
    )
    return s


@patch(
    "app.api.v1.search.search_query_service.es_suggest_mixed",
    new=AsyncMock(),
)
async def test_suggest_empty_when_elasticsearch_url_missing(
    client: AsyncClient,
) -> None:
    with patch(
        "app.api.v1.search.settings", _mock_settings(elasticsearch_url="")
    ):
        r = await client.get(
            "/api/v1/search/suggest", params={"q": "hi"}
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("items") == []


async def test_suggest_with_mock_results(
    client: AsyncClient,
) -> None:
    with (
        patch(
            "app.api.v1.search.settings",
            _mock_settings(
                elasticsearch_url="http://localhost:9200"
            ),
        ),
        patch(
            "app.api.v1.search.search_query_service.es_suggest_mixed",
            new=AsyncMock(
                return_value=[
                    SuggestItem(
                        kind="track", id=1, title="T", name=None
                    )
                ]
            ),
        ),
        patch("app.api.v1.search.es_available", return_value=True),
    ):
        r = await client.get(
            "/api/v1/search/suggest", params={"q": "a"}
        )
    assert r.status_code == 200
    data = r.json()["items"]
    assert len(data) == 1
    assert data[0]["kind"] == "track"
    assert data[0]["id"] == 1
