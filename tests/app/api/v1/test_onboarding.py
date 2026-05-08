from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_status_unauthenticated(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/onboarding/status")
    assert r.status_code == 401


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_status_new_user(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8001)
    headers = await auth_headers(client, 8001)

    r = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["onboarding_completed"] is False
    assert data["calibration_completed"] is False
    assert data["import_prompt_acknowledged"] is False
    assert "can_import_from_telegram" in data
    assert "has_telegram_profile_music" in data


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_import_ack(
    mock_preflight: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_preflight.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8010)
    headers = await auth_headers(client, 8010)

    r = await client.post(
        "/api/v1/onboarding/import-ack",
        headers=headers,
    )
    assert r.status_code == 200

    r2 = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert r2.json()["import_prompt_acknowledged"] is True


async def test_get_genres(
    client: AsyncClient,
) -> None:
    r = await client.get("/api/v1/onboarding/genres")
    assert r.status_code == 200
    genres = r.json()
    assert isinstance(genres, list)
    assert len(genres) >= 10


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_save_preferences(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8002)
    headers = await auth_headers(client, 8002)

    r = await client.post(
        "/api/v1/onboarding/preferences",
        json={
            "genres": ["rock", "pop", "jazz"],
            "artist_ids": [],
            "moods": ["chill"],
        },
        headers=headers,
    )
    assert r.status_code == 200

    r2 = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert r2.json()["onboarding_completed"] is True


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_complete(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8003)
    headers = await auth_headers(client, 8003)

    r = await client.post(
        "/api/v1/onboarding/complete",
        headers=headers,
    )
    assert r.status_code == 200

    r2 = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    d = r2.json()
    assert d["onboarding_completed"] is True
    assert d["import_prompt_acknowledged"] is True


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_profile_defaults_telegram(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8004)
    headers = await auth_headers(client, 8004)

    r = await client.get(
        "/api/v1/onboarding/profile-defaults",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["suggested_display_name"]
    assert body["auth_provider"] == "telegram"
    assert body["suggested_avatar_url"]


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_submit_profile_updates_user(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8005)
    headers = await auth_headers(client, 8005)

    r = await client.post(
        "/api/v1/onboarding/profile",
        json={
            "display_name": "MyNewName",
            "locale": "ru-RU",
            "use_default_avatar": False,
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "MyNewName"
    assert body["profile_completed"] is True

    status = await client.get(
        "/api/v1/onboarding/status",
        headers=headers,
    )
    assert status.json()["profile_completed"] is True


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_bootstrap(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8006)
    headers = await auth_headers(client, 8006)

    r = await client.get(
        "/api/v1/onboarding/bootstrap",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "profile_defaults" in body
    assert "genre_bubbles" in body
    assert isinstance(body["genre_bubbles"], list)
    assert "show_import_offer" in body


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_taste_swipe_batch(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8007)
    headers = await auth_headers(client, 8007)

    r = await client.post(
        "/api/v1/onboarding/taste-swipe",
        json={
            "decisions": [],
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["saved"] == 0


@patch(
    "app.services.onboarding_service.preflight_telegram_profile_music",
    new_callable=AsyncMock,
)
async def test_submit_profile_invalid_name_keeps_user(
    mock_pf: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_pf.return_value = MagicMock(
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    await create_test_user(client, 8008)
    headers = await auth_headers(client, 8008)

    r = await client.post(
        "/api/v1/onboarding/profile",
        json={
            "display_name": "   ",
            "locale": None,
            "use_default_avatar": False,
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"]
