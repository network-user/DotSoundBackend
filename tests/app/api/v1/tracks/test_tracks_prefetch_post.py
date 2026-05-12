from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


@patch(
    "app.services.audio_cache_prefetch.prefetch_track_urls",
    new_callable=AsyncMock,
)
async def test_tracks_prefetch_post_202(
    _warm: AsyncMock,
    client: AsyncClient,
) -> None:
    await create_test_user(client, 88201)
    headers = await auth_headers(client, 88201)
    r = await client.post(
        "/api/v1/tracks/prefetch",
        json={"track_ids": [1, 2, 3]},
        headers=headers,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 3


@patch(
    "app.services.audio_cache_prefetch.prefetch_track_urls",
    new_callable=AsyncMock,
)
async def test_tracks_prefetch_post_respects_cap_when_setting_zero(
    _warm: AsyncMock,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "audio_cache_prefetch_max_ids",
        0,
    )
    await create_test_user(client, 88202)
    headers = await auth_headers(client, 88202)
    r = await client.post(
        "/api/v1/tracks/prefetch",
        json={"track_ids": [9, 8, 7, 6, 5]},
        headers=headers,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 1
    _warm.assert_awaited_once_with([9])
