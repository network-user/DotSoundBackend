from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q
from tests.conftest import (
    auth_headers,
    create_test_user,
)

pytestmark = pytest.mark.anyio


@patch(
    "app.core.s3.upload_object",
    new_callable=AsyncMock,
    return_value=None,
)
@patch(
    "app.services.file_validator.validate_audio",
    return_value=None,
)
@patch(
    "app.services.upload_service.transcode_and_upload.kiq",
    new_callable=AsyncMock,
    return_value=None,
)
@patch(
    "app.services.upload_service.generate_and_upload_cover.kiq",
    new_callable=AsyncMock,
    return_value=None,
)
@patch(
    "app.services.search_index_notify.schedule_reindex_track",
    new_callable=AsyncMock,
    return_value=None,
)
async def test_upload_enqueues_feature_jobs(
    _r: object,
    _g: object,
    _t: object,
    _c: object,
    _s: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    u = await create_test_user(
        client,
        telegram_id=555001,
    )
    uid = int(u["id"])
    hdr = await auth_headers(
        client,
        uid,
    )
    data = {
        "title": "T",
        "upload_terms_accepted": "true",
    }
    r = await client.post(
        "/api/v1/tracks/upload",
        data=data,
        headers=hdr,
        files={
            "file": (
                "t.mp3",
                BytesIO(
                    b"\xff\xfb" + b"\x00" * 64
                ),
                "audio/mpeg",
            )
        },
    )
    assert r.status_code == 201
    tid = int(r.json()["id"])
    rows = (
        await db_session.execute(
            select(ComputeJob.job_type).where(
                ComputeJob.target_id == str(tid)
            )
        )
    ).all()
    jt = {str(row[0]) for row in rows}
    assert q.JOB_TRACK_AUDIO_FEATURES in jt
    assert q.JOB_CATALOG_INGEST_NORMALIZE in jt
