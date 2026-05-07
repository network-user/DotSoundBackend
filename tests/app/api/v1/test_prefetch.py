"""Stateless tests for ``GET /api/v1/prefetch/policy``.

The endpoint is DB-less: we mount only the prefetch router on a
fresh FastAPI app to isolate it from the rest of the test fixture
graph (which otherwise spins up a SQLite schema for unrelated
models).
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.prefetch import router as prefetch_router
from app.core.rate_limit import limiter

pytestmark = pytest.mark.anyio


@pytest.fixture
def standalone_app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(prefetch_router, prefix="/api/v1")
    return app


@pytest.fixture
async def standalone_client(
    standalone_app: FastAPI,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=standalone_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


async def test_prefetch_policy_default(
    standalone_client: AsyncClient,
) -> None:
    response = await standalone_client.get("/api/v1/prefetch/policy")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["skip_third_party_audio_cache"] is True
    assert body["eviction_policy"] == "lru"
    assert body["hot_pool_size"] >= 1
    assert body["concurrent_prefetch_limit"] >= 1
    assert body["max_storage_bytes"] > 0
    look = body["lookahead_by_context"]
    for key in (
        "home",
        "album",
        "artist",
        "playlist",
        "radio",
        "playback",
        "queue",
        "deep_link",
    ):
        assert key in look
    assert look["album"] == 5
    assert look["home"] == 3


async def test_prefetch_policy_save_data_disables_cold(
    standalone_client: AsyncClient,
) -> None:
    response = await standalone_client.get(
        "/api/v1/prefetch/policy",
        params={
            "save_data": "true",
            "effective_type": "4g",
        },
    )
    assert response.status_code == 200
    body = response.json()
    look = body["lookahead_by_context"]
    assert look["home"] == 0
    assert look["album"] == 0
    assert look["search_results"] == 0
    assert look["radio"] == 1
    assert look["playback"] == 1
    assert body["warm_segments_per_track"] == 1


async def test_prefetch_policy_3g_halves(
    standalone_client: AsyncClient,
) -> None:
    response = await standalone_client.get(
        "/api/v1/prefetch/policy",
        params={"effective_type": "3g"},
    )
    body = response.json()
    look = body["lookahead_by_context"]
    assert look["home"] == 1
    assert look["album"] == 2
    assert look["radio"] == 2


async def test_prefetch_policy_quota_caps_storage(
    standalone_client: AsyncClient,
) -> None:
    huge = 50 * 1024 * 1024 * 1024
    response = await standalone_client.get(
        "/api/v1/prefetch/policy",
        params={"quota_bytes": huge},
    )
    body = response.json()
    assert body["max_storage_bytes"] == 200 * 1024 * 1024


async def test_prefetch_policy_unknown_effective_type_default(
    standalone_client: AsyncClient,
) -> None:
    response = await standalone_client.get(
        "/api/v1/prefetch/policy",
        params={"effective_type": "lte"},
    )
    body = response.json()
    look = body["lookahead_by_context"]
    assert look["home"] == 3
    assert look["album"] == 5
