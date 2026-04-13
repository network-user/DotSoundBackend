import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_hls_master_track_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/hls/master.m3u8",
    )
    assert r.status_code == 404


async def test_hls_variant_invalid_variant(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 110001)
    track = await create_test_track(
        client, "HLS Track",
        uploader_id=user["id"],
    )
    r = await client.get(
        f"/api/v1/tracks/{track['id']}"
        "/hls/invalid/playlist.m3u8",
    )
    assert r.status_code == 400


async def test_hls_segment_invalid_name(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 110002)
    track = await create_test_track(
        client, "HLS Seg Track",
        uploader_id=user["id"],
    )
    r = await client.get(
        f"/api/v1/tracks/{track['id']}"
        "/hls/hi/bad_segment",
    )
    assert r.status_code in (400, 404)


async def test_hls_segment_track_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/tracks/99999/hls/hi/000.ts",
    )
    assert r.status_code == 404
