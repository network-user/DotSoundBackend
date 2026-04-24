"""Tests for search query helpers (ES mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import search_query_service as svs


def test_base_track_filters_playable() -> None:
    f = svs._base_track_filters(playable_only=True)
    assert len(f) == 3
    assert any(
        b.get("term", {}).get("playable") is True for b in f
    )


def test_base_track_filters_all() -> None:
    f = svs._base_track_filters(playable_only=False)
    assert len(f) == 2
    assert not any(
        b.get("term", {}).get("playable")
        is True
        for b in f
    )


@pytest.mark.anyio
async def test_es_search_tracks_returns_none_without_es() -> None:
    with patch.object(
        svs, "es_available", return_value=False
    ):
        r = await svs.es_search_tracks(
            "a", page=1, size=10, playable_only=True
        )
        assert r is None


@pytest.mark.anyio
async def test_es_search_tracks_empty_q() -> None:
    with patch.object(svs, "es_available", return_value=True):
        r = await svs.es_search_tracks(
            "   ", page=1, size=10, playable_only=True
        )
        assert r is None


@pytest.mark.anyio
async def test_es_search_tracks_success() -> None:
    es = MagicMock()
    es.search = AsyncMock(
        return_value={
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_source": {"track_id": 1}},
                    {"_id": "2", "_source": {}},
                ],
            }
        }
    )
    with (
        patch.object(svs, "es_available", return_value=True),
        patch.object(svs, "get_es", return_value=es),
    ):
        ids, total = await svs.es_search_tracks(
            "x", page=1, size=10, playable_only=True
        )
    assert total == 2
    assert ids == [1, 2]


@pytest.mark.anyio
async def test_es_search_tracks_on_exception() -> None:
    es = MagicMock()
    es.search = AsyncMock(side_effect=OSError("es down"))
    with (
        patch.object(svs, "es_available", return_value=True),
        patch.object(svs, "get_es", return_value=es),
    ):
        r = await svs.es_search_tracks(
            "q", page=1, size=2, playable_only=True
        )
    assert r is None


@pytest.mark.anyio
async def test_es_suggest_mixed_without_es() -> None:
    with patch.object(
        svs, "es_available", return_value=False
    ):
        r = await svs.es_suggest_mixed("ab")
        assert r is None
