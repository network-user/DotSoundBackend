"""abuse_events table for anti-abuse signal aggregation

Persists short-lived abuse signals (failed login bursts,
register collisions, opaque client-token hashes seen across
multiple accounts). Retention is bounded -- a daily prune task
deletes rows older than the policy-defined window.

* ``signal_hash``  -- 64-char hex of the opaque client-side
                      token (canvas / webgl / UA-class etc.).
                      Plain string, indexed.
* ``ip_masked``    -- IP after PrivateCore mask (no full IP).
* ``user_id``      -- nullable FK; pre-auth events have no user.
* ``kind``         -- ``register|login|play|upload``.
* ``score``        -- decision score from PrivateCore policy.

Revision ID: 0088
Revises: 0087
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "abuse_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "signal_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "ip_masked",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_abuse_events_created_at",
        "abuse_events",
        ["created_at"],
    )
    op.create_index(
        "ix_abuse_events_signal_hash_created",
        "abuse_events",
        ["signal_hash", "created_at"],
    )
    op.create_index(
        "ix_abuse_events_ip_created",
        "abuse_events",
        ["ip_masked", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_abuse_events_ip_created",
        table_name="abuse_events",
    )
    op.drop_index(
        "ix_abuse_events_signal_hash_created",
        table_name="abuse_events",
    )
    op.drop_index(
        "ix_abuse_events_created_at",
        table_name="abuse_events",
    )
    op.drop_table("abuse_events")
