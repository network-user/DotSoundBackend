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


def test_hls_storage_prefix_cas() -> None:
    from app.api.v1.tracks.hls import _hls_storage_prefix

    cas_master = (
        "hls-blobs/ab/abcdef0123456789abcdef0123456789"
        "abcdef0123456789abcdef0123456789/master.m3u8"
    )
    assert _hls_storage_prefix(42, cas_master) == (
        "hls-blobs/ab/abcdef0123456789abcdef0123456789"
        "abcdef0123456789abcdef0123456789"
    )


def test_hls_storage_prefix_legacy_track_id() -> None:
    from app.api.v1.tracks.hls import _hls_storage_prefix

    legacy = "hls/42/master.m3u8"
    assert _hls_storage_prefix(42, legacy) == "hls/42"


def test_hls_storage_prefix_falls_back_to_legacy_when_unknown() -> None:
    from app.api.v1.tracks.hls import _hls_storage_prefix

    assert _hls_storage_prefix(7, None) == "hls/7"
    assert _hls_storage_prefix(7, "weird/key.txt") == "hls/7"


async def test_clear_stale_hls_manifest_resets_key_when_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lazy-heal: when ``/hls/master.m3u8`` raises 404 we drop the
    dangling ``hls_manifest_key`` so the next play short-circuits to
    progressive (the schema's ``has_hls`` becomes false).
    """
    from unittest.mock import AsyncMock, MagicMock

    from app.api.v1.tracks.hls import _clear_stale_hls_manifest

    fake_track = MagicMock()
    fake_track.hls_manifest_key = "hls/42/master.m3u8"

    fake_session = MagicMock()
    fake_session.get = AsyncMock(return_value=fake_track)
    fake_session.commit = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr(
        "app.api.v1.tracks.hls.AsyncSessionLocal",
        lambda: fake_session,
    )

    await _clear_stale_hls_manifest(42, "hls/42/master.m3u8")

    assert fake_track.hls_manifest_key is None
    fake_session.commit.assert_awaited_once()


async def test_clear_stale_hls_manifest_skips_when_key_already_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a transcoder re-attached a fresh bundle between the 404 and
    the cleanup, we must NOT wipe the new key."""
    from unittest.mock import AsyncMock, MagicMock

    from app.api.v1.tracks.hls import _clear_stale_hls_manifest

    fake_track = MagicMock()
    fake_track.hls_manifest_key = "hls-blobs/fresh/master.m3u8"

    fake_session = MagicMock()
    fake_session.get = AsyncMock(return_value=fake_track)
    fake_session.commit = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr(
        "app.api.v1.tracks.hls.AsyncSessionLocal",
        lambda: fake_session,
    )

    await _clear_stale_hls_manifest(42, "hls/42/master.m3u8")

    assert fake_track.hls_manifest_key == "hls-blobs/fresh/master.m3u8"
    fake_session.commit.assert_not_awaited()
