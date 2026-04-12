from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio


async def test_tracks_my_ignores_user_id_query(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(
        client, 800001, first_name="Owner"
    )
    viewer = await create_test_user(
        client, 800002, first_name="Viewer"
    )
    owner_track = await create_test_track(
        client, "Owner Track", owner["id"]
    )
    viewer_headers = await auth_headers(
        client, viewer["id"]
    )

    response = await client.get(
        f"/api/v1/tracks/my?user_id={owner['id']}",
        headers=viewer_headers,
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert owner_track["id"] not in ids


async def test_soundcloud_import_requires_auth(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/soundcloud/import",
        json={
            "sc_url": "https://soundcloud.com/test/track",
            "is_public": True,
        },
    )

    assert response.status_code == 401


async def test_soundcloud_import_uses_current_user(
    client: AsyncClient,
) -> None:
    owner = await create_test_user(
        client, 800003, first_name="Importer"
    )
    other = await create_test_user(
        client, 800004, first_name="Other"
    )
    headers = await auth_headers(
        client, owner["id"]
    )
    sc_url = "https://soundcloud.com/test/owned-track"
    sc_data = {
        "kind": "track",
        "permalink_url": sc_url,
        "title": "Owned Track",
        "user": {"username": "Artist"},
        "duration": 123000,
        "uri": "sc:owned-track",
    }

    with patch(
        "app.services.soundcloud_service.SoundCloudService.resolve_url",
        new=AsyncMock(return_value=sc_data),
    ):
        response = await client.post(
            "/api/v1/soundcloud/import",
            json={
                "sc_url": sc_url,
                "is_public": False,
                "uploader_id": other["id"],
            },
            headers=headers,
        )

    assert response.status_code == 201
    assert response.json()["uploaded_by_id"] == owner["id"]
