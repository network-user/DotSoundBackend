"""Tests for ES indexing helpers (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.track import Track
from app.services import search_index_service as idx


@pytest.mark.anyio
async def test_index_track_document_skips_without_es() -> None:
    session = MagicMock()
    t = MagicMock(spec=Track)
    t.id = 1
    t.is_active = True
    t.is_public = True
    with patch.object(idx, "es_available", return_value=False):
        await idx.index_track_document(session, t)  # no raise


def test_indexable_track() -> None:
    t = MagicMock()
    t.is_active = True
    t.is_public = True
    assert idx._indexable_track(t) is True
    t.is_active = False
    assert idx._indexable_track(t) is False
