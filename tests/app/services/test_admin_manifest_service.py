from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.admin_capability import (
    AdminCapabilityRepository,
)
from app.services.admin_manifest_service import (
    KNOWN_CAPABILITIES,
    build_manifest,
)

pytestmark = pytest.mark.anyio


async def test_build_manifest_backfills_capabilities_when_initialized(
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=88001001,
        first_name="Root",
        is_admin=True,
        admin_init=True,
        admin_totp_enabled=True,
    )
    db_session.add(user)
    await db_session.flush()

    manifest = await build_manifest(db_session, user, locale="ru")

    repo = AdminCapabilityRepository(db_session)
    stored = await repo.list_for_user(user.id)
    assert len(stored) == len(KNOWN_CAPABILITIES)
    assert len(manifest["menu"]) > 2
    assert len(manifest["capabilities"]) == len(KNOWN_CAPABILITIES)

    manifest_again = await build_manifest(db_session, user, locale="ru")
    stored_2 = await repo.list_for_user(user.id)
    assert len(stored_2) == len(KNOWN_CAPABILITIES)
    assert manifest_again["capabilities"] == manifest["capabilities"]


async def test_build_manifest_skips_backfill_before_admin_init(
    db_session: AsyncSession,
) -> None:
    user = User(
        telegram_id=88001002,
        first_name="Fresh",
        is_admin=True,
        admin_init=False,
        admin_totp_enabled=False,
    )
    db_session.add(user)
    await db_session.flush()

    manifest = await build_manifest(db_session, user, locale="ru")
    repo = AdminCapabilityRepository(db_session)
    assert await repo.list_for_user(user.id) == []
    assert [m["id"] for m in manifest["menu"]] == ["dashboard"]
