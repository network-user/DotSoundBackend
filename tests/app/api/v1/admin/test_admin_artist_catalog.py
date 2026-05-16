from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
)
from app.models.track import Track
from app.services.admin_artist_catalog_service import (
    AdminArtistCatalogService,
)
from tests.conftest import admin_bearer_for_user, create_test_user

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def no_catalog_progress_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    async def _no_snapshot(_artist_id: int) -> None:
        return None

    monkeypatch.setattr(
        "app.services.admin_artist_catalog_service.acsp.set_running",
        _noop,
    )
    monkeypatch.setattr(
        "app.services.admin_artist_catalog_service.acsp.get_snapshot",
        _no_snapshot,
    )


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


async def test_admin_catalog_station_probe_reports_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140002)
    h = await admin_bearer_for_user(
        client,
        db_session,
        user_id=admin["id"],
    )
    artist = Artist(
        name="Probe Artist",
        name_normalized="probe artist",
        soundcloud_user_id=777001,
    )
    db_session.add(artist)
    await db_session.commit()

    mock_sc = AsyncMock()
    mock_sc.fetch_expanded_artist_station_playlist.return_value = {
        "id": -1000000000777001,
        "title": "Probe station",
        "tracks": [
            {
                "urn": "soundcloud:tracks:11",
                "kind": "track",
                "title": "Station Track",
                "permalink_url": "https://soundcloud.com/a/b",
                "user": {"username": "Other Artist"},
                "streamable": True,
            }
        ],
    }

    with patch(
        "app.services.admin_artist_catalog_service.SoundCloudService",
        return_value=mock_sc,
    ):
        r = await client.get(
            f"/api/v1/admin/artists/{artist.id}" "/catalog/station-probe",
            headers=h,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["station_status"] == "ok"
    assert body["fetched_track_count"] == 1
    assert body["importable_track_count"] == 1
    assert body["tracks"][0]["ref"] == "soundcloud:tracks:11"
    assert body["tracks"][0]["artist"] == "Other Artist"


async def test_admin_list_artists_search(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_test_user(client, 140011)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    db_session.add_all(
        [
            Artist(
                name="Needle Artist",
                name_normalized="needle artist",
                soundcloud_permalink="needle-profile",
                enrichment_status="done",
            ),
            Artist(
                name="Other Artist",
                name_normalized="other artist",
                enrichment_status="pending",
            ),
        ]
    )
    await db_session.commit()

    async def _snap(_artist_id: int) -> dict:
        return {
            "state": "running",
            "mode": "full",
            "updated_at": "2026-05-15T00:00:00+00:00",
        }

    monkeypatch.setattr(
        "app.api.v1.admin.artist_catalog.acsp.get_snapshot",
        _snap,
    )
    r = await client.get(
        "/api/v1/admin/artists",
        headers=h,
        params={
            "q": "needle",
            "enrichment": "done",
            "page": 1,
            "size": 10,
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Needle Artist"
    assert body["items"][0]["catalog_sync_state"] == "running"
    assert body["items"][0]["catalog_sync_mode"] == "full"

    r2 = await client.get(
        "/api/v1/admin/artists",
        headers=h,
        params={"q": "needle-profile", "page": 1, "size": 10},
    )

    assert r2.status_code == 200
    assert r2.json()["total"] == 1

    r3 = await client.get(
        "/api/v1/admin/artists",
        headers=h,
        params={
            "q": "needle",
            "catalog_sync": "running",
            "page": 1,
            "size": 10,
        },
    )

    assert r3.status_code == 200
    assert r3.json()["total"] == 1


async def test_admin_list_artist_ids_match_filters(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_test_user(client, 140012)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    ready = Artist(
        name="Needle Bulk Artist",
        name_normalized="needle bulk artist",
        soundcloud_permalink="needle-bulk-profile",
        enrichment_status="done",
    )
    pending = Artist(
        name="Waiting Bulk Artist",
        name_normalized="waiting bulk artist",
        soundcloud_permalink="waiting-bulk-profile",
        enrichment_status="pending",
    )
    db_session.add_all([ready, pending])
    await db_session.commit()
    await db_session.refresh(ready)
    await db_session.refresh(pending)

    r = await client.get(
        "/api/v1/admin/artists/ids",
        headers=h,
        params={"q": "Needle Bulk", "enrichment": "done"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["ids"] == [ready.id]

    async def _snap(artist_id: int) -> dict | None:
        if artist_id == pending.id:
            return {
                "state": "running",
                "mode": "full",
                "updated_at": "2026-05-15T00:00:00+00:00",
            }
        return None

    monkeypatch.setattr(
        "app.api.v1.admin.artist_catalog.acsp.get_snapshot",
        _snap,
    )
    r2 = await client.get(
        "/api/v1/admin/artists/ids",
        headers=h,
        params={
            "q": "Waiting Bulk",
            "catalog_sync": "running",
        },
    )

    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["total"] == 1
    assert body2["ids"] == [pending.id]


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
    assert r0.json()["catalog_sync_state"] == "idle"

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


async def test_admin_catalog_overview_reflects_redis_sync_snapshot(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_test_user(client, 140009)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(name="Snap", name_normalized="snap")
    db_session.add(artist)
    await db_session.commit()

    async def _snap(_aid: int) -> dict:
        return {
            "state": "success",
            "mode": "full",
            "soundcloud_album_id": None,
            "detail": {"albums_synced": 2, "albums_seen": 2},
            "updated_at": "2026-01-02T00:00:00+00:00",
        }

    monkeypatch.setattr(
        "app.services.admin_artist_catalog_service.acsp.get_snapshot",
        _snap,
    )
    r = await client.get(
        f"/api/v1/admin/artists/{artist.id}/catalog/overview",
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["catalog_sync_state"] == "success"
    assert body["catalog_sync_mode"] == "full"
    assert body["catalog_sync_detail"]["albums_synced"] == 2
    assert body["catalog_sync_updated_at"] == "2026-01-02T00:00:00+00:00"


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

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.background_jobs.enqueue",
            new_callable=AsyncMock,
            return_value="job-full",
        ) as kiq,
    ):
        r1 = await client.post(
            f"/api/v1/admin/artists/{artist.id}/catalog/sync",
            headers=h,
        )
        assert r1.status_code == 200
        assert r1.json()["task"] == "sync_artist_catalog_task"
        assert r1.json()["job_id"] == "job-full"
        kiq.assert_awaited_once()

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.background_jobs.enqueue",
            new_callable=AsyncMock,
            return_value="job-release",
        ) as kiq2,
    ):
        r2 = await client.post(
            (
                f"/api/v1/admin/artists/{artist.id}/catalog/"
                f"releases/{rel.id}/sync"
            ),
            headers=h,
        )
        assert r2.status_code == 200
        assert r2.json()["soundcloud_album_id"] == 999001
        assert r2.json()["job_id"] == "job-release"
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

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.background_jobs.enqueue",
            new_callable=AsyncMock,
            return_value="job-full-after-cooldown",
        ) as kiq,
    ):
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

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.background_jobs.enqueue",
            new_callable=AsyncMock,
            return_value="job-full-after-cooldown",
        ) as kiq,
        patch(
            "app.services.soundcloud_service.SoundCloudService."
            "try_autofill_soundcloud_user_id_for_artist",
            new_callable=AsyncMock,
        ) as autofill,
    ):
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

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.background_jobs.enqueue",
            new_callable=AsyncMock,
            return_value="job-full-after-cooldown",
        ) as kiq,
    ):
        r = await client.post(
            f"/api/v1/admin/artists/{artist.id}/catalog/sync",
            headers=h,
        )
        assert r.status_code == 200
        kiq.assert_awaited_once()


async def test_admin_catalog_bulk_sync_queues_and_reports_errors(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140010)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(
        name="BulkOk",
        name_normalized="bulkok",
        soundcloud_user_id=555001,
    )
    missing_sc = Artist(name="BulkNoSc", name_normalized="bulknosc")
    db_session.add_all([artist, missing_sc])
    await db_session.commit()

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.background_jobs.enqueue",
            new_callable=AsyncMock,
            return_value="job-bulk",
        ) as enqueue,
        patch(
            "app.services.soundcloud_service.SoundCloudService."
            "try_autofill_soundcloud_user_id_for_artist",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        r = await client.post(
            "/api/v1/admin/artists/catalog/sync-batch",
            headers=h,
            json={"artist_ids": [artist.id, missing_sc.id, artist.id]},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["queued"] == 1
    assert body["job_ids"][str(artist.id)] == "job-bulk"
    assert body["errors"] == [
        {
            "artist_id": missing_sc.id,
            "detail": "artist has no soundcloud_user_id",
        }
    ]
    enqueue.assert_awaited_once()


async def test_admin_artist_bulk_enrich_queues_and_reports_errors(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140012)
    h = await admin_bearer_for_user(client, db_session, user_id=admin["id"])
    artist = Artist(name="BulkEnrich", name_normalized="bulkenrich")
    db_session.add(artist)
    await db_session.commit()

    with patch(
        "app.services.background_jobs.enqueue",
        new_callable=AsyncMock,
        return_value="job-enrich",
    ) as enqueue:
        r = await client.post(
            "/api/v1/admin/artists/enrich-batch",
            headers=h,
            json={"artist_ids": [artist.id, 999999, artist.id]},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["queued"] == 1
    assert body["job_ids"][str(artist.id)] == "job-enrich"
    assert body["errors"] == [
        {"artist_id": 999999, "detail": "artist not found"}
    ]
    enqueue.assert_awaited_once()


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
