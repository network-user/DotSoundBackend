from __future__ import annotations

import json
import secrets
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.services import compute_queue_service as q
from app.services import compute_worker_service as cws

pytestmark = pytest.mark.anyio


def _w_headers(
    worker: object,
    method: str,
    path: str,
    body: bytes,
) -> dict[str, str]:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    sig = cws._compute_signature(
        worker.token_hash,
        method,
        path,
        ts,
        nonce,
        body,
    )
    return {
        "X-Worker-Id": worker.id,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Worker-Signature": sig,
    }


def _mock_redis() -> MagicMock:
    m = MagicMock()
    m.set = AsyncMock(return_value=True)
    m.incr = AsyncMock(return_value=1)
    m.expire = AsyncMock()
    return MagicMock(
        return_value=m,
    )


_APIM = "app.api.v1.internal.compute_jobs"
_WCS = "app.services.compute_worker_service"
_ALL = "app.middlewares.internal_api_allowlist"


@patch(
    f"{_APIM}.rl.check_and_consume",
    new_callable=AsyncMock,
)
@patch(
    f"{_ALL}.is_ip_in_cidrs",
    return_value=True,
)
@patch(
    f"{_WCS}.get_redis_client",
    new_callable=_mock_redis,
)
async def test_compute_claim_204(
    _r: object,
    _a: object,
    _l: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    w, _s = await cws.register_worker(
        db_session,
        name="w",
        profile="cpu_light",
    )
    await db_session.commit()
    body = json.dumps(
        {"job_types": [q.JOB_TRACK_AUDIO_FEATURES]}
    ).encode("utf-8")
    h = _w_headers(
        w,
        "POST",
        "/api/v1/internal/compute/jobs/claim",
        body,
    )
    h["content-type"] = "application/json"
    r = await client.post(
        "/api/v1/internal/compute/jobs/claim",
        content=body,
        headers=h,
    )
    assert r.status_code == 204


@patch(
    f"{_APIM}.rl.check_and_consume",
    new_callable=AsyncMock,
)
@patch(
    f"{_ALL}.is_ip_in_cidrs",
    return_value=True,
)
@patch(
    f"{_WCS}.get_redis_client",
    new_callable=_mock_redis,
)
async def test_compute_claim_returns_job_with_audio_url(
    _r: object,
    _a: object,
    _l: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    w, _s = await cws.register_worker(
        db_session,
        name="w2",
        profile="cpu_light",
    )
    t = Track(
        title="a",
        source="internal",
    )
    db_session.add(t)
    await db_session.flush()
    await q.enqueue(
        db_session,
        job_type=q.JOB_TRACK_AUDIO_FEATURES,
        target_kind=q.TARGET_KIND_TRACK,
        target_id=t.id,
    )
    await db_session.commit()
    body = json.dumps(
        {"job_types": [q.JOB_TRACK_AUDIO_FEATURES]}
    ).encode("utf-8")
    h = _w_headers(
        w,
        "POST",
        "/api/v1/internal/compute/jobs/claim",
        body,
    )
    h["content-type"] = "application/json"
    r = await client.post(
        "/api/v1/internal/compute/jobs/claim",
        content=body,
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()
    assert "audio_url" in data
    assert "internal/compute/jobs/" in data["audio_url"]


@patch(
    f"{_APIM}.rl.check_and_consume",
    new_callable=AsyncMock,
)
@patch(
    f"{_ALL}.is_ip_in_cidrs",
    return_value=True,
)
@patch(
    f"{_WCS}.get_redis_client",
    new_callable=_mock_redis,
)
async def test_compute_result_ok(
    _r: object,
    _a: object,
    _l: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    w, _s = await cws.register_worker(
        db_session,
        name="w3",
        profile="cpu_light",
    )
    t = Track(
        title="b",
        source="internal",
    )
    db_session.add(t)
    await db_session.flush()
    await q.enqueue(
        db_session,
        job_type=q.JOB_TRACK_AUDIO_FEATURES,
        target_kind=q.TARGET_KIND_TRACK,
        target_id=t.id,
    )
    await db_session.commit()
    cl = await q.claim_next(
        db_session,
        worker_id=w.id,
        job_types=[q.JOB_TRACK_AUDIO_FEATURES],
    )
    assert cl is not None
    j_id = cl.id
    await db_session.commit()
    pl = json.dumps(
        {"feature_vector": [0.1], "mood_tags": ["a"]}
    ).encode("utf-8")
    h = _w_headers(
        w,
        "POST",
        f"/api/v1/internal/compute/jobs/{j_id}/result",
        pl,
    )
    h["content-type"] = "application/json"
    r = await client.post(
        f"/api/v1/internal/compute/jobs/{j_id}/result",
        content=pl,
        headers=h,
    )
    assert r.status_code == 200
