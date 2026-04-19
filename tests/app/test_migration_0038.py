from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
)


pytestmark = pytest.mark.anyio


async def test_admin_auth_tables_present(
    db_engine: AsyncEngine,
) -> None:
    """The 0038 migration adds three admin tables and four user
    columns. Conftest builds the schema from `Base.metadata`, so
    presence of the tables is the proof that all models were
    registered correctly.
    """
    async with db_engine.connect() as conn:
        from sqlalchemy import inspect

        def _check(sync_conn) -> dict[str, bool]:
            insp = inspect(sync_conn)
            return {
                "admin_devices": insp.has_table(
                    "admin_devices"
                ),
                "admin_sessions": insp.has_table(
                    "admin_sessions"
                ),
                "admin_login_attempts": insp.has_table(
                    "admin_login_attempts"
                ),
                "admin_capabilities": insp.has_table(
                    "admin_capabilities"
                ),
                "admin_actions_log": insp.has_table(
                    "admin_actions_log"
                ),
                "app_settings": insp.has_table(
                    "app_settings"
                ),
            }

        result = await conn.run_sync(_check)
    for name, present in result.items():
        assert present, (
            f"table {name} missing from schema"
        )


async def test_user_admin_columns_present(
    db_engine: AsyncEngine,
) -> None:
    async with db_engine.connect() as conn:
        from sqlalchemy import inspect

        def _columns(sync_conn) -> list[str]:
            insp = inspect(sync_conn)
            return [
                c["name"]
                for c in insp.get_columns(
                    "users"
                )
            ]

        cols = await conn.run_sync(_columns)
    for required in (
        "admin_init",
        "admin_totp_secret_encrypted",
        "admin_totp_enabled",
        "admin_backup_codes_hash",
    ):
        assert (
            required in cols
        ), f"users.{required} missing"
