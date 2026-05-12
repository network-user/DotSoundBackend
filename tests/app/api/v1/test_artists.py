import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio


async def test_list_artists_empty(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/artists")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_get_artist_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/artists/99999")
    assert r.status_code == 404


async def test_artist_tracks_empty(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/artists/99999/tracks"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_artist_share_card_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/artists/99997/share-card",
    )
    assert r.status_code == 404


async def test_artist_share_card_ok(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from dotsound_private_core.services.artist_normalizer import (
        normalize_name,
    )

    from app.models.artist import Artist

    row = Artist(
        name="Share Card Artist",
        name_normalized=normalize_name("Share Card Artist"),
        source="internal",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    r = await client.get(
        f"/api/v1/artists/{row.id}/share-card",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["artist_id"] == row.id
    assert body["display_name"] == "Share Card Artist"
    assert "/artist/" in body["profile_url"]
