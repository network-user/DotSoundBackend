"""Integration tests for admin track context endpoints."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    admin_bearer_for_user,
    auth_headers,
    create_test_track,
    create_test_user,
)

pytestmark = pytest.mark.anyio

_BASE = "/api/v1/admin/tracks"


async def test_get_context_no_existing_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140001)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Track No Context", uploader_id=user["id"]
    )

    r = await client.get(
        f"{_BASE}/{track['id']}/context", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["content"] is None
    assert data["track_id"] == track["id"]


async def test_set_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140002)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Track Set Context", uploader_id=user["id"]
    )

    r = await client.patch(
        f"{_BASE}/{track['id']}/context",
        json={"content": "Test description"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "done"
    assert data["content"] == "Test description"


async def test_set_context_too_long(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140003)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Track Long", uploader_id=user["id"]
    )

    r = await client.patch(
        f"{_BASE}/{track['id']}/context",
        json={"content": "x" * 5001},
        headers=headers,
    )
    assert r.status_code == 422


async def test_get_after_set_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140004)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Track Get After Set", uploader_id=user["id"]
    )

    await client.patch(
        f"{_BASE}/{track['id']}/context",
        json={"content": "Saved info"},
        headers=headers,
    )

    r = await client.get(
        f"{_BASE}/{track['id']}/context", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["content"] == "Saved info"
    assert data["status"] == "done"


async def test_clear_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140005)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Track Clear", uploader_id=user["id"]
    )

    await client.patch(
        f"{_BASE}/{track['id']}/context",
        json={"content": "Will be cleared"},
        headers=headers,
    )

    r = await client.delete(
        f"{_BASE}/{track['id']}/context", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_found"
    assert data["content"] is None


async def test_get_prompt_russian_artist(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140006)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Группа крови", uploader_id=user["id"]
    )
    await _set_artist(client, db_session, track["id"], "Кино")

    r = await client.get(
        f"{_BASE}/{track['id']}/prompt", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["language"] == "ru"
    assert "Кино" in data["prompt"]
    assert "DotSound" in data["prompt"]


async def test_get_prompt_english_artist(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140007)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Yesterday", uploader_id=user["id"]
    )
    await _set_artist(
        client, db_session, track["id"], "The Beatles"
    )

    r = await client.get(
        f"{_BASE}/{track['id']}/prompt", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["language"] == "en"
    assert "The Beatles" in data["prompt"]


async def test_get_prompt_track_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140008)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )

    r = await client.get(
        f"{_BASE}/99999/prompt", headers=headers
    )
    assert r.status_code == 404


async def test_batch_prompt(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140009)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    t1 = await create_test_track(
        client, "Song One", uploader_id=user["id"]
    )
    t2 = await create_test_track(
        client, "Song Two", uploader_id=user["id"]
    )
    t3 = await create_test_track(
        client, "Song Three", uploader_id=user["id"]
    )

    r = await client.post(
        f"{_BASE}/context/batch-prompt",
        json={"track_ids": [t1["id"], t2["id"], t3["id"]]},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["track_count"] == 3
    assert str(t1["id"]) in data["prompt"]
    assert str(t2["id"]) in data["prompt"]
    assert str(t3["id"]) in data["prompt"]


async def test_batch_prompt_empty_list_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140010)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )

    r = await client.post(
        f"{_BASE}/context/batch-prompt",
        json={"track_ids": []},
        headers=headers,
    )
    assert r.status_code == 422


async def test_batch_import_valid_json(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140011)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    t1 = await create_test_track(
        client, "Import Track 1", uploader_id=user["id"]
    )
    t2 = await create_test_track(
        client, "Import Track 2", uploader_id=user["id"]
    )

    payload = json.dumps({
        "tracks": [
            {"id": t1["id"], "content": "Info about track 1"},
            {"id": t2["id"], "content": "Info about track 2"},
        ]
    })

    r = await client.post(
        f"{_BASE}/context/batch-import",
        json={"raw_response": payload},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 2
    assert data["errors"] == []

    r2 = await client.get(
        f"{_BASE}/{t1['id']}/context", headers=headers
    )
    assert r2.json()["content"] == "Info about track 1"
    assert r2.json()["status"] == "done"


async def test_batch_import_partial_failure(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140012)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Partial Import", uploader_id=user["id"]
    )

    payload = json.dumps({
        "tracks": [
            {"id": track["id"], "content": "Good content"},
            {"id": "not-a-number", "content": "Bad ID"},
        ]
    })

    r = await client.post(
        f"{_BASE}/context/batch-import",
        json={"raw_response": payload},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 1
    assert len(data["errors"]) == 1


async def test_batch_import_invalid_json(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140013)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )

    r = await client.post(
        f"{_BASE}/context/batch-import",
        json={"raw_response": "this is not json at all"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 0
    assert len(data["errors"]) == 1


async def test_batch_import_markdown_fences(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await create_test_user(client, 140014)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=user["id"]
    )
    track = await create_test_track(
        client, "Fence Track", uploader_id=user["id"]
    )

    inner = json.dumps({
        "tracks": [{"id": track["id"], "content": "Markdown content"}]
    })
    raw = f"```json\n{inner}\n```"

    r = await client.post(
        f"{_BASE}/context/batch-import",
        json={"raw_response": raw},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 1
    assert data["errors"] == []


async def test_non_admin_context_rejected(
    client: AsyncClient,
) -> None:
    user = await create_test_user(client, 140015)
    headers = await auth_headers(client, user["id"])

    r = await client.get(
        f"{_BASE}/1/context", headers=headers
    )
    assert r.status_code == 401


# helpers

async def _set_artist(
    client: AsyncClient,
    db_session: AsyncSession,
    track_id: int,
    artist: str,
) -> None:
    from sqlalchemy import update

    from app.models.track import Track

    await db_session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(artist=artist)
    )
    await db_session.commit()
