"""Smoke test for compute_queue_service. Run via:

    poetry run python scripts/smoke_compute_queue.py

Used as a sanity check while pytest cannot run cleanly under the
local shell. Exits non-zero on any assertion failure.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import BigInteger, Boolean, event
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

import app.models  # noqa: F401  (register tables)
from app.models.base import Base
from app.models.compute_job import ComputeJob
from app.services import compute_queue_service as q


@compiles(BigInteger, "sqlite")
def _bi(_t, _c, **_k):
    return "INTEGER"


@event.listens_for(Base, "init", propagate=True)
def _bool_def(target, _a, kwargs):
    for attr in type(target).__mapper__.column_attrs:
        col = attr.columns[0]
        if (
            isinstance(col.type, Boolean)
            and attr.key not in kwargs
            and col.server_default is not None
        ):
            sd = col.server_default.arg
            if isinstance(sd, str):
                setattr(
                    target,
                    attr.key,
                    sd.lower() in ("true", "1"),
                )


async def main() -> None:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Sess = async_sessionmaker(eng, expire_on_commit=False)

    async with Sess() as s:
        # idempotent enqueue
        j1 = await q.enqueue(
            s,
            job_type="taf",
            target_kind="track",
            target_id=42,
            payload={"a": 1},
        )
        j2 = await q.enqueue(
            s,
            job_type="taf",
            target_kind="track",
            target_id=42,
            payload={"a": 2},
        )
        assert j1.id == j2.id, "idempotent FAIL"
        assert j1.payload == {"a": 1}, "preserve original FAIL"
        await s.commit()

        # claim
        c = await q.claim_next(
            s, worker_id="w1", job_types=["taf"]
        )
        assert c is not None
        assert c.status == q.STATUS_CLAIMED
        assert c.attempts == 1
        await s.commit()

        # success
        await q.mark_succeeded(
            s, job=c, result={"ok": True}
        )
        await s.commit()
        r = await s.get(ComputeJob, j1.id)
        assert r.status == q.STATUS_SUCCEEDED
        assert r.result == {"ok": True}

        # priority
        low = await q.enqueue(
            s,
            job_type="t",
            target_kind="x",
            target_id="1",
            priority=0,
        )
        high = await q.enqueue(
            s,
            job_type="t",
            target_kind="x",
            target_id="2",
            priority=10,
        )
        await s.commit()
        first = await q.claim_next(
            s, worker_id="w", job_types=["t"]
        )
        assert (
            first.id == high.id
        ), f"priority FAIL: {first.id} != {high.id}"
        await s.commit()

        # retry-with-backoff -> terminal failure
        job = await q.enqueue(
            s,
            job_type="r",
            target_kind="x",
            target_id="1",
            max_attempts=2,
        )
        await s.commit()
        c = await q.claim_next(
            s, worker_id="w", job_types=["r"]
        )
        await q.mark_failed(s, job=c, reason="boom")
        await s.commit()
        r = await s.get(ComputeJob, job.id)
        assert r.status == q.STATUS_PENDING
        assert r.last_error == "boom"

        r.next_attempt_at = datetime.now(timezone.utc)
        await s.commit()
        c2 = await q.claim_next(
            s, worker_id="w", job_types=["r"]
        )
        assert c2.attempts == 2
        await q.mark_failed(s, job=c2, reason="boom2")
        await s.commit()
        r = await s.get(ComputeJob, job.id)
        assert (
            r.status == q.STATUS_FAILED
        ), f"expected FAILED, got {r.status}"

        # stale claim recovery
        sj = await q.enqueue(
            s,
            job_type="s",
            target_kind="x",
            target_id="1",
        )
        await s.commit()
        c = await q.claim_next(
            s, worker_id="w", job_types=["s"]
        )
        c.claim_deadline_at = datetime.now(
            timezone.utc
        ) - timedelta(minutes=5)
        await s.commit()
        n = await q.requeue_stale_claims(s)
        await s.commit()
        assert n == 1
        r = await s.get(ComputeJob, sj.id)
        assert r.status == q.STATUS_PENDING
        assert r.claimed_by is None

        # depth + dead-letter
        depth = await q.queue_depth(s)
        dl = await q.dead_letter_jobs(s)
        assert len(dl) == 1

        print(
            "OK depth=",
            depth,
            "dead_letter=",
            len(dl),
            flush=True,
        )

    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
