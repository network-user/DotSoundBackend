from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql

from app.repositories.admin import AdminRepository


class _PostgresSession:
    def __init__(self) -> None:
        self._engine = create_engine(
            "postgresql+asyncpg://u:p@localhost/db"
        )

    def get_bind(self):
        return self._engine


def test_synced_lines_present_postgres_uses_case_guarded_length() -> None:
    repo = AdminRepository(_PostgresSession())
    expr = repo._synced_lines_present()
    sql = str(
        expr.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "jsonb_typeof" in sql
    assert "CASE WHEN" in sql
    assert "jsonb_array_length" in sql
