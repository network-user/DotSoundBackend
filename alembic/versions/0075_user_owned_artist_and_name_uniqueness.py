"""user owned artist and name uniqueness

Revision ID: 0075
Revises: 0074
Create Date: 2026-05-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def _normalize_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = " ".join(raw.strip().split()).lower()
    return value or None


def _dedupe_users_display_names(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, display_name FROM users "
            "WHERE display_name IS NOT NULL "
            "ORDER BY id ASC"
        )
    ).fetchall()
    taken: set[str] = set()
    for row in rows:
        user_id = int(row.id)
        raw = str(row.display_name)
        base = _normalize_name(raw)
        if not base:
            bind.execute(
                sa.text(
                    "UPDATE users SET display_name = NULL, "
                    "display_name_normalized = NULL WHERE id = :id"
                ),
                {"id": user_id},
            )
            continue
        final_name = raw.strip()
        final_norm = base
        suffix = 2
        while final_norm in taken:
            final_name = f"{raw.strip()} {suffix}"
            final_norm = _normalize_name(final_name) or (
                f"user-{user_id}-{suffix}"
            )
            suffix += 1
        taken.add(final_norm)
        bind.execute(
            sa.text(
                "UPDATE users SET display_name = :name, "
                "display_name_normalized = :norm WHERE id = :id"
            ),
            {"id": user_id, "name": final_name, "norm": final_norm},
        )


def _dedupe_artists(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, name FROM artists "
            "ORDER BY id ASC"
        )
    ).fetchall()
    user_names = {
        str(x[0])
        for x in bind.execute(
            sa.text(
                "SELECT display_name_normalized FROM users "
                "WHERE display_name_normalized IS NOT NULL"
            )
        ).fetchall()
    }
    taken = set(user_names)
    for row in rows:
        artist_id = int(row.id)
        raw_name = str(row.name)
        base = _normalize_name(raw_name) or f"artist-{artist_id}"
        final_name = raw_name.strip() or f"Artist {artist_id}"
        final_norm = base
        suffix = 2
        while final_norm in taken:
            final_name = f"{raw_name.strip() or 'Artist'} {suffix}"
            final_norm = _normalize_name(final_name) or (
                f"artist-{artist_id}-{suffix}"
            )
            suffix += 1
        taken.add(final_norm)
        bind.execute(
            sa.text(
                "UPDATE artists SET name = :name, name_normalized = :norm "
                "WHERE id = :id"
            ),
            {"id": artist_id, "name": final_name, "norm": final_norm},
        )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "display_name_normalized",
            sa.String(length=128),
            nullable=True,
        ),
    )
    op.add_column(
        "artists",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_artists_owner_user_id_users",
        "artists",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    _dedupe_users_display_names(bind)
    _dedupe_artists(bind)

    op.create_unique_constraint(
        "uq_users_display_name_normalized",
        "users",
        ["display_name_normalized"],
    )
    op.create_unique_constraint(
        "uq_artists_name_normalized",
        "artists",
        ["name_normalized"],
    )
    op.create_unique_constraint(
        "uq_artists_owner_user_id",
        "artists",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_users_display_name_normalized",
        "users",
        ["display_name_normalized"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_display_name_normalized", table_name="users")
    op.drop_constraint("uq_artists_owner_user_id", "artists", type_="unique")
    op.drop_constraint("uq_artists_name_normalized", "artists", type_="unique")
    op.drop_constraint(
        "uq_users_display_name_normalized", "users", type_="unique"
    )
    op.drop_constraint(
        "fk_artists_owner_user_id_users", "artists", type_="foreignkey"
    )
    op.drop_column("artists", "owner_user_id")
    op.drop_column("users", "display_name_normalized")
