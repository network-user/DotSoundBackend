from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.artist import ArtistRepository
from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


async def _make_admin(
    db_session: AsyncSession, user_id: int
) -> None:
    await db_session.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_admin=True)
    )
    await db_session.commit()


async def _make_artist(
    db_session: AsyncSession, name: str
) -> int:
    repo = ArtistRepository(db_session)
    artist = await repo.create(
        name=name,
        name_normalized=name.lower(),
        source="internal",
        external_id=None,
    )
    await db_session.commit()
    return artist.id


def _mock_provider(info):
    return patch.dict(
        "sys.modules",
        {
            "dotsound_private_core.services.artist_info_provider": SimpleNamespace(
                fetch_artist_info=AsyncMock(
                    return_value=info
                ),
                warmup_artist_info_provider=lambda: None,
            ),
        },
    )


async def test_enrich_endpoint_admin_success(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140001)
    await _make_admin(db_session, admin["id"])
    headers = await auth_headers(client, admin["id"])
    artist_id = await _make_artist(db_session, "Test Artist")

    info = SimpleNamespace(
        bio="A test bio",
        birth_date=None,
        birthplace="Berlin",
        country="de",
        image_url=None,
        website_url=None,
        confidence=0.9,
    )

    with _mock_provider(info):
        r = await client.post(
            f"/api/v1/artists/{artist_id}/enrich",
            headers=headers,
        )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == artist_id
    assert data["bio"] == "A test bio"
    assert data["country"] == "DE"
    assert data["enrichment_status"] == "done"


async def test_enrich_endpoint_non_admin_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140002)
    headers = await auth_headers(client, user["id"])
    artist_id = await _make_artist(db_session, "Blocked Artist")

    r = await client.post(
        f"/api/v1/artists/{artist_id}/enrich",
        headers=headers,
    )
    assert r.status_code == 403


async def test_enrich_endpoint_missing_artist(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 140003)
    await _make_admin(db_session, admin["id"])
    headers = await auth_headers(client, admin["id"])

    r = await client.post(
        "/api/v1/artists/99999/enrich",
        headers=headers,
    )
    assert r.status_code == 404


async def test_enrich_endpoint_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    artist_id = await _make_artist(db_session, "Anon Artist")
    r = await client.post(
        f"/api/v1/artists/{artist_id}/enrich"
    )
    assert r.status_code == 401


async def test_resolve_artist_by_name_exact(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    artist_id = await _make_artist(db_session, "Exact Name")
    r = await client.get(
        "/api/v1/artists/resolve",
        params={"name": "Exact Name"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == artist_id


async def test_resolve_artist_by_name_not_found(
    client: AsyncClient,
) -> None:
    r = await client.get(
        "/api/v1/artists/resolve",
        params={"name": "No Such Artist"},
    )
    assert r.status_code == 404


async def test_get_artist_returns_new_fields(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    artist_id = await _make_artist(db_session, "Fields")
    r = await client.get(f"/api/v1/artists/{artist_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["enrichment_status"] == "pending"
    assert data["birth_date"] is None
    assert data["age"] is None
    assert "image_url" in data
    assert "country" in data
    assert "website_url" in data
