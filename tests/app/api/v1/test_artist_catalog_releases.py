from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.models.artist_catalog import (
    ArtistCatalogRelease,
    ArtistCatalogReleaseTrack,
)
from app.models.track import Track

pytestmark = pytest.mark.anyio


async def test_catalog_releases_artist_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/artists/99998/catalog/releases")
    assert r.status_code == 404


async def test_catalog_release_detail_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/artists/99997/catalog/releases/1")
    assert r.status_code == 404


async def test_catalog_releases_empty_then_populated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    artist = Artist(name="CatArt", name_normalized="catart")
    db_session.add(artist)
    await db_session.flush()

    r = await client.get(f"/api/v1/artists/{artist.id}/catalog/releases")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}

    tr = Track(title="One", play_count=0)
    db_session.add(tr)
    await db_session.flush()
    rel = ArtistCatalogRelease(
        artist_id=artist.id,
        title="EP",
        release_kind="album",
        released_at=date(2024, 1, 15),
        soundcloud_album_id=9001,
        display_position=0,
        cover_key="covers/x.png",
    )
    db_session.add(rel)
    await db_session.flush()
    db_session.add(
        ArtistCatalogReleaseTrack(
            release_id=rel.id,
            track_id=tr.id,
            position=0,
        )
    )
    await db_session.commit()

    r2 = await client.get(f"/api/v1/artists/{artist.id}/catalog/releases")
    assert r2.status_code == 200
    data = r2.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["id"] == rel.id
    assert item["title"] == "EP"
    assert item["release_kind"] == "album"
    assert item["released_at"] == "2024-01-15"
    assert item["display_position"] == 0
    assert item["track_count"] == 1
    assert "cover_proxy" in item["cover_url"]

    r3 = await client.get(
        f"/api/v1/artists/{artist.id}/catalog/releases/{rel.id}"
    )
    assert r3.status_code == 200
    detail = r3.json()
    assert detail["title"] == "EP"
    assert len(detail["tracks"]) == 1
    assert detail["tracks"][0]["position"] == 0
    assert detail["tracks"][0]["track"]["id"] == tr.id
    assert detail["tracks"][0]["track"]["title"] == "One"


async def test_catalog_release_wrong_artist_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    a1 = Artist(name="A1", name_normalized="a1")
    a2 = Artist(name="A2", name_normalized="a2")
    db_session.add_all([a1, a2])
    await db_session.flush()
    rel = ArtistCatalogRelease(
        artist_id=a1.id,
        title="Mine",
        soundcloud_album_id=42,
        display_position=0,
    )
    db_session.add(rel)
    await db_session.commit()

    r = await client.get(f"/api/v1/artists/{a2.id}/catalog/releases/{rel.id}")
    assert r.status_code == 404


async def test_artist_catalog_read_service(
    db_session: AsyncSession,
) -> None:
    from app.services.artist_catalog_read_service import (
        ArtistCatalogReadService,
    )

    artist = Artist(name="S", name_normalized="s")
    db_session.add(artist)
    await db_session.flush()
    svc = ArtistCatalogReadService(db_session)
    lst = await svc.list_releases(artist.id)
    assert lst is not None
    assert lst.total == 0

    assert await svc.get_release_detail(artist.id, 1) is None
