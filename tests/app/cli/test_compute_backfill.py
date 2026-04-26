from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
)

from app.cli import compute_backfill as cb

pytestmark = pytest.mark.anyio


async def test_backfill_dry_run_uses_patched_session(
    db_engine,
) -> None:
    factory = async_sessionmaker(
        db_engine, expire_on_commit=False
    )
    with patch.object(
        cb,
        "AsyncSessionLocal",
        factory,
    ):
        code = await cb.run(
            [
                "--type",
                "track_audio_features",
                "--limit",
                "0",
                "--dry-run",
            ],
        )
    assert code == 0
