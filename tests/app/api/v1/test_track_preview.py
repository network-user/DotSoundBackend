from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_blob import AudioBlob
from app.models.track import Track
from app.models.user import User
from tests.conftest import auth_headers, create_test_user

pytestmark = pytest.mark.anyio


@patch(
    "app.api.v1.track_preview.transcode_http_audio_to_fmp4_aac",
    new_callable=AsyncMock,
    return_value=b"\x00\x00\x00\x20ftyp",
)
@patch(
    "app.core.s3.get_presigned_url",
    new_callable=AsyncMock,
    return_value="https://minio.test/in",
)
async def test_track_preview_segment(
    _m_tr: AsyncMock,
    _m_s3: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    uinfo = await create_test_user(client, 88099)
    uid = int(uinfo["id"])
    r_u = await db_session.execute(
        select(User).where(User.id == uid)
    )
    u = r_u.scalar_one()
    b = AudioBlob(
        content_sha256="f" * 64,
        s3_key="k",
        content_type="audio/mpeg",
        size_bytes=10,
        ref_count=0,
    )
    db_session.add(b)
    await db_session.flush()
    t = Track(
        title="Preview T",
        duration_seconds=60,
        file_key="audio/p.mp3",
        blob_id=b.id,
        is_active=True,
        is_public=True,
        play_count=0,
        uploaded_by_id=u.id,
    )
    db_session.add(t)
    await db_session.flush()
    tid = t.id
    await db_session.commit()
    headers = await auth_headers(client, 88099)
    r = await client.get(
        f"/api/v1/track-preview/{tid}/segment.mp4",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/mp4")
    assert b"ftyp" in r.content
    assert "max-age=86400" in (r.headers.get("cache-control") or "")
