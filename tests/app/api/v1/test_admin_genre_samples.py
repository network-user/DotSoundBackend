import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.models.user import User
from tests.conftest import (
    admin_bearer_for_user,
    create_test_user,
    grant_admin_capability,
)

pytestmark = pytest.mark.anyio


async def _insert_track(
    session: AsyncSession, uploader_tg: int, sha: str
) -> int:
    u = User(
        telegram_id=uploader_tg,
        first_name="A",
    )
    session.add(u)
    await session.flush()
    b = AudioBlob(
        content_sha256=sha,
        s3_key="k",
        content_type="audio/mpeg",
        size_bytes=10,
        ref_count=0,
    )
    session.add(b)
    await session.flush()
    t = Track(
        title="Admin sample",
        genre="Rock",
        duration_seconds=60,
        file_key="a/b.mp3",
        blob_id=b.id,
        is_active=True,
        is_public=True,
        play_count=0,
        uploaded_by_id=u.id,
    )
    session.add(t)
    await session.flush()
    return t.id


async def test_genre_samples_admin_list_add_delete(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    track_id = await _insert_track(
        db_session, 131000, "9" * 64
    )
    await db_session.commit()
    admin = await create_test_user(client, 131001)
    await grant_admin_capability(
        db_session,
        admin["id"],
        "recsys.genre_samples.manage",
    )
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    r0 = await client.get(
        "/api/v1/admin/genre-samples?genre=Rock",
        headers=headers,
    )
    assert r0.status_code == 200
    assert r0.json()["items"] == []
    r1 = await client.post(
        "/api/v1/admin/genre-samples/Rock",
        json={"track_id": track_id, "position": 0},
        headers=headers,
    )
    assert r1.status_code == 201
    row_id = r1.json()["id"]
    r2 = await client.get(
        "/api/v1/admin/genre-samples?genre=Rock",
        headers=headers,
    )
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1
    r3 = await client.delete(
        f"/api/v1/admin/genre-samples/{row_id}",
        headers=headers,
    )
    assert r3.status_code == 204
