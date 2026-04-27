from __future__ import annotations

import asyncio

import pytest

from app.services import import_queue_dispatcher as mod

pytestmark = pytest.mark.anyio


async def test_stop_dispatcher_noop_when_no_task() -> None:
    mod._dispatcher_task = None
    await mod.stop_dispatcher_task()
    assert mod._dispatcher_task is None


async def test_stop_dispatcher_noop_when_task_done() -> None:
    async def done_coro() -> None:
        return

    t = asyncio.create_task(done_coro())
    await t
    mod._dispatcher_task = t
    await mod.stop_dispatcher_task()
    assert mod._dispatcher_task is None


async def test_stop_dispatcher_cancels_pending_and_clears() -> None:
    async def long_sleep() -> None:
        try:
            await asyncio.sleep(3600.0)
        except asyncio.CancelledError:
            raise

    t = asyncio.create_task(long_sleep())
    mod._dispatcher_task = t
    await mod.stop_dispatcher_task()
    assert mod._dispatcher_task is None
    assert t.done()
    assert t.cancelled()
