from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track
from app.services.admin_artist_catalog_service import (
    AdminArtistCatalogService,
)
from tests.conftest import admin_bearer_for_user, create_test_user

pytestmark = pytest.mark.anyio


async def test_admin_catalog_overview_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140001)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    r = await client.get(
        "/api/v1/admin/artists/99991/catalog/overview",
        headers=h,
    )
    assert r.status_code == 404


async def test_admin_catalog_crud_and_reorder(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140002)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(name="Ac", name_normalized="ac")
    db_session.add(artist)
    await db_session.flush()
    tr = Track(title="T1", play_count=0)
    db_session.add(tr)
    await db_session.flush()
    await db_session.commit()

    r0 = await client.get(
        f"/api/v1/admin/artists/{artist.id}/catalog/overview",
        headers=h,
    )
    assert r0.status_code == 200
    assert r0.json()["releases_total"] == 0

    r1 = await client.post(
        f"/api/v1/admin/artists/{artist.id}/catalog/releases",
        headers=h,
        json={"title": "Manual EP", "manual_lock": True},
    )
    assert r1.status_code == 201
    rid = r1.json()["id"]

    r2 = await client.patch(
        f"/api/v1/admin/artists/{artist.id}/catalog/releases/{rid}",
        headers=h,
        json={"title": "Manual EP v2"},
    )
    assert r2.status_code == 200
    assert r2.json()["title"] == "Manual EP v2"

    r3 = await client.put(
        f"/api/v1/admin/artists/{artist.id}/catalog/releases/{rid}/tracks",
        headers=h,
        json={"track_ids": [tr.id]},
    )
    assert r3.status_code == 200
    assert len(r3.json()["tracks"]) == 1

    r4 = await client.put(
        f"/api/v1/admin/artists/{artist.id}/catalog/release-display-order",
        headers=h,
        json={"ordered_release_ids": [rid]},
    )
    assert r4.status_code == 204

    r5 = await client.delete(
        f"/api/v1/admin/artists/{artist.id}/catalog/releases/{rid}",
        headers=h,
    )
    assert r5.status_code == 204


async def test_admin_catalog_soundcloud_patch_duplicate(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140003)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    a1 = Artist(
        name="X1",
        name_normalized="x1",
        soundcloud_user_id=777001,
    )
    a2 = Artist(name="X2", name_normalized="x2")
    db_session.add_all([a1, a2])
    await db_session.commit()

    r = await client.patch(
        f"/api/v1/admin/artists/{a2.id}/catalog/soundcloud",
        headers=h,
        json={"soundcloud_user_id": 777001},
    )
    assert r.status_code == 400


async def test_admin_catalog_sync_requires_step_up(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140004)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(
        name="SyncMe",
        name_normalized="syncme",
        soundcloud_user_id=888001,
    )
    db_session.add(artist)
    await db_session.flush()
    rel = ArtistCatalogRelease(
        artist_id=artist.id,
        title="Al",
        soundcloud_album_id=999001,
        display_position=0,
    )
    db_session.add(rel)
    await db_session.commit()

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=False,
    ):
        r0 = await client.post(
            f"/api/v1/admin/artists/{artist.id}/catalog/sync",
            headers=h,
        )
        assert r0.status_code == 403

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with patch(
            "app.services.artist_catalog_sync_worker.sync_artist_catalog_task.kiq",
            new_callable=AsyncMock,
        ) as kiq:
            r1 = await client.post(
                f"/api/v1/admin/artists/{artist.id}/catalog/sync",
                headers=h,
            )
            assert r1.status_code == 200
            assert r1.json()["task"] == "sync_artist_catalog_task"
            kiq.assert_awaited_once()

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with patch(
            "app.services.artist_catalog_sync_worker.sync_artist_catalog_release_task.kiq",
            new_callable=AsyncMock,
        ) as kiq2:
            r2 = await client.post(
                f"/api/v1/admin/artists/{artist.id}/catalog/releases/{rel.id}/sync",
                headers=h,
            )
            assert r2.status_code == 200
            assert r2.json()["soundcloud_album_id"] == 999001
            kiq2.assert_awaited_once()


async def test_admin_catalog_full_sync_cooldown_429(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140006)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(
        name="Cd",
        name_normalized="cd",
        soundcloud_user_id=444001,
    )
    db_session.add(artist)
    await db_session.flush()
    rel = ArtistCatalogRelease(
        artist_id=artist.id,
        title="Synced",
        soundcloud_album_id=444002,
        display_position=0,
        synced_at=datetime.now(UTC) - timedelta(seconds=5),
    )
    db_session.add(rel)
    await db_session.commit()

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with patch(
            "app.services.artist_catalog_sync_worker.sync_artist_catalog_task.kiq",
            new_callable=AsyncMock,
        ) as kiq:
            r = await client.post(
                f"/api/v1/admin/artists/{artist.id}/catalog/sync",
                headers=h,
            )
            assert r.status_code == 429
            assert r.json()["detail"] == (
                AdminArtistCatalogService.COOLDOWN_ENQUEUE_DETAIL
            )
            kiq.assert_not_awaited()


async def test_admin_catalog_full_sync_calls_autofill_when_no_sc_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140008)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(name="NoScYet", name_normalized="noscyet")
    db_session.add(artist)
    await db_session.commit()

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with patch(
            "app.services.artist_catalog_sync_worker.sync_artist_catalog_task.kiq",
            new_callable=AsyncMock,
        ) as kiq:
            with patch(
                "app.services.soundcloud_service.SoundCloudService."
                "try_autofill_soundcloud_user_id_for_artist",
                new_callable=AsyncMock,
            ) as autofill:
                autofill.return_value = False
                r = await client.post(
                    f"/api/v1/admin/artists/{artist.id}/catalog/sync",
                    headers=h,
                )
                assert r.status_code == 400
                assert "soundcloud_user_id" in r.json()["detail"]
                autofill.assert_awaited_once_with(artist.id)
                kiq.assert_not_awaited()


async def test_admin_catalog_full_sync_after_cooldown_ok(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140007)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(
        name="Cd2",
        name_normalized="cd2",
        soundcloud_user_id=444010,
    )
    db_session.add(artist)
    await db_session.flush()
    rel = ArtistCatalogRelease(
        artist_id=artist.id,
        title="Old",
        soundcloud_album_id=444011,
        display_position=0,
        synced_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db_session.add(rel)
    await db_session.commit()

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with patch(
            "app.services.artist_catalog_sync_worker.sync_artist_catalog_task.kiq",
            new_callable=AsyncMock,
        ) as kiq:
            r = await client.post(
                f"/api/v1/admin/artists/{artist.id}/catalog/sync",
                headers=h,
            )
            assert r.status_code == 200
            kiq.assert_awaited_once()


async def test_admin_catalog_search_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140005)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(name="SearchArt", name_normalized="searchart")
    db_session.add(artist)
    await db_session.flush()
    tr = Track(
        title="UniqueZebraTitle",
        artist="SearchArt",
        play_count=0,
    )
    db_session.add(tr)
    await db_session.flush()
    from app.models.artist import TrackArtist

    db_session.add(
        TrackArtist(
            track_id=tr.id,
            artist_id=artist.id,
            role="primary",
            position=0,
        )
    )
    await db_session.commit()

    r = await client.get(
        f"/api/v1/admin/artists/{artist.id}/catalog/tracks/search",
        headers=h,
        params={"search": "Zebra", "page": 1, "size": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    ids = {it["id"] for it in data["items"]}
    assert tr.id in ids
