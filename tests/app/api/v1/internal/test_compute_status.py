from __future__ import annotations

import secrets
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import compute_queue_service as q
from app.services import compute_worker_service as cws

pytestmark = pytest.mark.anyio


def _h(
    w: object,
    path: str,
) -> dict[str, str]:
    b = b""
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    sig = cws._compute_signature(
        w.token_hash,
        "GET",
        path,
        ts,
        nonce,
        b,
    )
    return {
        "X-Worker-Id": w.id,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Worker-Signature": sig,
    }


def _m() -> MagicMock:
    m = MagicMock()
    m.set = AsyncMock(return_value=True)
    m.incr = AsyncMock(return_value=1)
    m.expire = AsyncMock()
    return MagicMock(
        return_value=m,
    )


_AP = "app.api.v1.internal.compute_jobs"
_WC = "app.services.compute_worker_service"
_AL = "app.middlewares.internal_api_allowlist"


@patch(
    f"{_AP}.rl.check_and_consume",
    new_callable=AsyncMock,
)
@patch(
    f"{_AL}.is_ip_in_cidrs",
    return_value=True,
)
@patch(
    f"{_WC}.get_redis_client",
    new_callable=_m,
)
async def test_get_status(
    _r: object,
    _a: object,
    _l: object,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    w, _ = await cws.register_worker(
        db_session,
        name="ws",
        profile="cpu_light",
    )
    await q.enqueue(
        db_session,
        job_type=q.JOB_TRACK_AUDIO_FEATURES,
        target_kind="track",
        target_id=1,
    )
    await db_session.commit()
    hdr = _h(
        w,
        "/api/v1/internal/compute/status",
    )
    r = await client.get(
        "/api/v1/internal/compute/status",
        headers=hdr,
    )
    assert r.status_code == 200
    js = r.json()
    assert "by_type" in js
    assert "oldest_pending_sec" in js
