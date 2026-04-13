import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from app.models.base import Base

pytestmark = pytest.mark.anyio

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_EXPECTED_TABLES = {
    "users",
    "tracks",
    "albums",
    "playlists",
    "playlist_tracks",
    "likes",
    "dislikes",
    "user_follows",
    "complaints",
    "track_comments",
    "comment_hides",
    "comment_votes",
    "track_lyrics",
    "notifications",
    "import_jobs",
    "account_merges",
    "user_blocks",
    "conversations",
    "conversation_members",
    "messages",
    "message_reactions",
    "message_attachments",
    "encryption_keys",
    "user_eq_settings",
    "login_history",
}


async def _create_engine_with_tables():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _get_table_names(engine) -> list[str]:
    async with engine.connect() as conn:

        def _inspect(connection):
            return inspect(connection).get_table_names()

        return await conn.run_sync(_inspect)


async def _get_columns(
    engine, table: str
) -> list[str]:
    async with engine.connect() as conn:

        def _inspect(connection):
            return [
                c["name"]
                for c in inspect(connection).get_columns(
                    table
                )
            ]

        return await conn.run_sync(_inspect)


async def test_metadata_creates_all_tables() -> None:
    engine = await _create_engine_with_tables()
    tables = set(await _get_table_names(engine))
    missing = _EXPECTED_TABLES - tables
    assert not missing, f"Missing tables: {missing}"
    await engine.dispose()


async def test_user_table_has_key_columns() -> None:
    engine = await _create_engine_with_tables()
    columns = await _get_columns(engine, "users")
    for col in (
        "id",
        "telegram_id",
        "email",
        "is_admin",
        "first_name",
        "auth_provider",
    ):
        assert col in columns, f"Missing column: {col}"
    await engine.dispose()


async def test_track_table_has_key_columns() -> None:
    engine = await _create_engine_with_tables()
    columns = await _get_columns(engine, "tracks")
    for col in (
        "id",
        "title",
        "file_key",
        "uploaded_by_id",
        "processing_status",
        "is_public",
    ):
        assert col in columns, f"Missing column: {col}"
    await engine.dispose()


async def test_album_table_has_key_columns() -> None:
    engine = await _create_engine_with_tables()
    columns = await _get_columns(engine, "albums")
    for col in ("id", "title", "owner_id", "is_public"):
        assert col in columns, f"Missing column: {col}"
    await engine.dispose()


async def test_playlist_table_has_key_columns() -> None:
    engine = await _create_engine_with_tables()
    columns = await _get_columns(engine, "playlists")
    for col in (
        "id",
        "name",
        "owner_id",
        "is_public",
    ):
        assert col in columns, f"Missing column: {col}"
    await engine.dispose()
