"""add upload terms acceptance fields

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "track_upload_meta",
        sa.Column(
            "upload_terms_accepted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "track_upload_meta",
        sa.Column(
            "upload_terms_version",
            sa.String(length=32),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "track_upload_meta",
        "upload_terms_version",
    )
    op.drop_column(
        "track_upload_meta",
        "upload_terms_accepted",
    )
