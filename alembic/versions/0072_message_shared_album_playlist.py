"""add shared album and playlist ids to messages

Revision ID: 0072_msg_share_album_playlist
Revises: 0071
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0072_msg_share_album_playlist"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("shared_album_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("shared_playlist_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_shared_album_id_albums",
        "messages",
        "albums",
        ["shared_album_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_messages_shared_playlist_id_playlists",
        "messages",
        "playlists",
        ["shared_playlist_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_messages_shared_playlist_id_playlists",
        "messages",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_messages_shared_album_id_albums",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "shared_playlist_id")
    op.drop_column("messages", "shared_album_id")
