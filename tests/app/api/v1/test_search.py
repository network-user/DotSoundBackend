"""API tests for /search routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.search_query_service import SuggestItem

pytestmark = pytest.mark.anyio


def _mock_settings(
    **kwargs: str | bool,
) -> MagicMock:
    s = MagicMock()
    s.elasticsearch_enabled = kwargs.get("elasticsearch_enabled", True)
    s.elasticsearch_url = kwargs.get("elasticsearch_url", "")
    s.elasticsearch_index_tracks = kwargs.get(
        "elasticsearch_index_tracks", "t"
    )
    s.elasticsearch_index_artists = kwargs.get(
        "elasticsearch_index_artists", "a"
    )
    return s


@patch(
    "app.api.v1.search.search_query_service.es_suggest_mixed",
    new=AsyncMock(),
)
async def test_suggest_empty_when_elasticsearch_url_missing(
    client: AsyncClient,
) -> None:
    with patch(
        "app.api.v1.search.settings", _mock_settings(elasticsearch_url="")
    ):
        r = await client.get(
            "/api/v1/search/suggest", params={"q": "hi"}
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("items") == []


async def test_suggest_with_mock_results(
    client: AsyncClient,
) -> None:
    with (
        patch(
            "app.api.v1.search.settings",
            _mock_settings(
                elasticsearch_url="http://localhost:9200"
            ),
        ),
        patch(
            "app.api.v1.search.search_query_service.es_suggest_mixed",
            new=AsyncMock(
                return_value=[
                    SuggestItem(
                        kind="track", id=1, title="T", name=None
                    )
                ]
            ),
        ),
        patch("app.api.v1.search.es_available", return_value=True),
    ):
        r = await client.get(
            "/api/v1/search/suggest", params={"q": "a"}
        )
    assert r.status_code == 200
    data = r.json()["items"]
    assert len(data) == 1
    assert data[0]["kind"] == "track"
    assert data[0]["id"] == 1


async def test_authors_q_empty_validation(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/search/authors", params={"q": ""})
    assert r.status_code == 422


async def test_authors_empty_when_no_match(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    u = User(telegram_id=88001, first_name="Zed", username="zed88001")
    db_session.add(u)
    await db_session.commit()
    r = await client.get(
        "/api/v1/search/authors",
        params={"q": "zzznonexistentquery"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_authors_excludes_user_without_public_upload(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    u = User(
        telegram_id=88002,
        first_name="Lonely",
        username="lonely88002",
        display_name="Lonely Artist",
    )
    db_session.add(u)
    await db_session.commit()
    r = await client.get(
        "/api/v1/search/authors",
        params={"q": "Lonely"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_authors_includes_user_with_public_track_and_avatar_url(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    u = User(
        telegram_id=88003,
        first_name="First",
        last_name="Last",
        username="maker88003",
        display_name="Display Maker",
        avatar_key="avatars/unit-test-key.png",
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(
        Track(
            title="Song",
            artist="Self",
            duration_seconds=120,
            source_platform="soundcloud",
            source_url="https://sc.com/u88003",
            sc_url="https://soundcloud.com/unique88003",
            is_active=True,
            is_public=True,
            uploaded_by_id=u.id,
        )
    )
    await db_session.commit()
    with patch(
        "app.api.v1.search.s3.get_presigned_url",
        new=AsyncMock(return_value="https://signed.example/avatar"),
    ):
        r = await client.get(
            "/api/v1/search/authors",
            params={"q": "Maker"},
        )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == u.id
    assert items[0]["display_name"] == "Display Maker"
    assert items[0]["username"] == "maker88003"
    assert items[0]["avatar_url"] == "https://signed.example/avatar"


async def test_authors_multi_word_query_matches_display_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    u = User(
        telegram_id=88010,
        first_name="Stage",
        display_name="Maladoy Prince",
        username="mp88010",
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(
        Track(
            title="Hit",
            artist="Maladoy Prince",
            duration_seconds=60,
            source_platform="soundcloud",
            source_url="https://sc.com/u88010",
            sc_url="https://soundcloud.com/unique88010",
            is_active=True,
            is_public=True,
            uploaded_by_id=u.id,
        )
    )
    await db_session.commit()
    r = await client.get(
        "/api/v1/search/authors",
        params={"q": "maladoy prince"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == u.id
    assert items[0]["display_name"] == "Maladoy Prince"


async def test_authors_dicebear_when_no_avatar_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    u = User(
        telegram_id=88004,
        first_name="No",
        last_name="Photo",
        username="nophoto88004",
        avatar_seed="fixedseed88004",
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(
        Track(
            title="Song2",
            artist="Self",
            duration_seconds=90,
            source_platform="soundcloud",
            source_url="https://sc.com/u88004",
            sc_url="https://soundcloud.com/unique88004",
            is_active=True,
            is_public=True,
            uploaded_by_id=u.id,
        )
    )
    await db_session.commit()
    r = await client.get(
        "/api/v1/search/authors",
        params={"q": "nophoto"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert "dicebear.com" in items[0]["avatar_url"]
    assert "fixedseed88004" in items[0]["avatar_url"]
