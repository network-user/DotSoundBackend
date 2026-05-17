"""End-to-end pause-chain coverage for the dispatcher panel.

Two complementary scenarios live here:

* :func:`test_pause_chain_blocks_enqueue_then_resumes_clears`
  exercises the Taskiq path through
  :func:`app.services.background_jobs.enqueue`. We monkeypatch
  ``is_task_paused`` instead of going through Redis so the test stays
  fully in-process (no Redis fixture needed).
* :func:`test_claim_next_skips_paused_compute_job_type` exercises the
  compute-queue path through :func:`compute_queue_service.claim_next`,
  ensuring a paused ``job_type`` is not handed to a worker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compute_job import ComputeJob
from app.models.compute_worker import ComputeWorker
from app.services import compute_queue_service as q

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
async def _register_worker(
    db_session: AsyncSession,
) -> AsyncIterator[None]:
    wid = "w_pause_test"
    existing = await db_session.get(ComputeWorker, wid)
    if existing is None:
        db_session.add(
            ComputeWorker(
                id=wid,
                name=wid,
                profile="cpu_light",
                token_hash="test",
                active=True,
                max_concurrent_jobs=4,
            )
        )
        await db_session.commit()
    yield


async def test_claim_next_skips_paused_compute_job_type(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A paused job_type must not be returned by claim_next."""
    await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=999,
    )
    await db_session.commit()

    async def _paused() -> set[str]:
        return {"track_audio_features"}

    monkeypatch.setattr(
        "app.services.task_pause_service.paused_task_set", _paused
    )

    claimed = await q.claim_next(
        db_session,
        worker_id="w_pause_test",
        job_types=["track_audio_features"],
    )
    assert claimed is None

    rows = (
        await db_session.execute(
            ComputeJob.__table__.select().where(ComputeJob.target_id == "999")
        )
    ).fetchall()
    assert len(rows) == 1
    assert rows[0].status == q.STATUS_PENDING


async def test_claim_next_resumes_after_unpaused(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After resume (empty paused set), the job becomes claimable."""
    await q.enqueue(
        db_session,
        job_type="track_audio_features",
        target_kind="track",
        target_id=1001,
    )
    await db_session.commit()

    paused_set: set[str] = {"track_audio_features"}

    async def _paused() -> set[str]:
        return set(paused_set)

    monkeypatch.setattr(
        "app.services.task_pause_service.paused_task_set", _paused
    )

    none_yet = await q.claim_next(
        db_session,
        worker_id="w_pause_test",
        job_types=["track_audio_features"],
    )
    assert none_yet is None

    paused_set.discard("track_audio_features")

    claimed = await q.claim_next(
        db_session,
        worker_id="w_pause_test",
        job_types=["track_audio_features"],
    )
    assert claimed is not None
    assert claimed.target_id == "1001"
    assert claimed.status == q.STATUS_CLAIMED


async def test_pause_chain_blocks_enqueue_then_resumes_clears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``background_jobs.enqueue`` must raise TaskPaused when paused.

    After resume (paused returns False), enqueue should succeed. We
    mock the Taskiq kick path and ``AsyncSessionLocal`` so the test
    has no Redis / DB / broker dependencies — the goal here is the
    control-flow guarantee, not the persistence layer.
    """
    from app.services.background_jobs import TaskPaused, enqueue

    class _Kicker:
        def with_labels(self, **_labels: str) -> _Kicker:
            return self

        async def kiq(self, **_payload: object) -> object:
            class _Sent:
                task_id = "kicked-task-id"

            return _Sent()

    class _FakeTask:
        task_name = "demo.task_for_pause_chain"

        def kicker(self) -> _Kicker:
            return _Kicker()

    paused_flag = {"value": True}

    async def _is_paused(_name: str) -> bool:
        return paused_flag["value"]

    monkeypatch.setattr(
        "app.services.background_jobs.is_task_paused", _is_paused
    )

    class _FakeSession:
        def add(self, _obj: object) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def flush(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def get(self, _model: object, _pk: object) -> None:
            return None

        async def __aenter__(self) -> _FakeSession:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(
        "app.services.background_jobs.AsyncSessionLocal",
        _FakeSession,
    )

    with pytest.raises(TaskPaused) as exc_info:
        await enqueue(_FakeTask())
    assert exc_info.value.task_name == "demo.task_for_pause_chain"

    paused_flag["value"] = False
    job_id = await enqueue(_FakeTask())
    assert isinstance(job_id, str) and len(job_id) >= 16
