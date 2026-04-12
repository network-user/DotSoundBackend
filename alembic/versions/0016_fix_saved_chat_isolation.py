"""fix saved chat isolation

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    conversations = sa.table(
        "conversations",
        sa.column("id", sa.BigInteger()),
        sa.column("type", sa.String()),
        sa.column("title", sa.String()),
        sa.column("created_by_id", sa.BigInteger()),
    )
    conversation_members = sa.table(
        "conversation_members",
        sa.column("conversation_id", sa.BigInteger()),
        sa.column("user_id", sa.BigInteger()),
        sa.column("role", sa.String()),
        sa.column("is_pinned", sa.Boolean()),
        sa.column("is_muted", sa.Boolean()),
        sa.column("last_read_message_id", sa.BigInteger()),
    )
    messages = sa.table(
        "messages",
        sa.column("id", sa.BigInteger()),
        sa.column("conversation_id", sa.BigInteger()),
        sa.column("sender_id", sa.BigInteger()),
        sa.column("reply_to_id", sa.BigInteger()),
    )

    saved_rows = bind.execute(
        sa.select(
            conversations.c.id,
            conversations.c.created_by_id,
        )
        .where(conversations.c.type == "saved")
        .order_by(
            conversations.c.created_by_id.asc(),
            conversations.c.id.asc(),
        )
    ).mappings().all()

    canonical_by_owner: dict[int, int] = {}
    for row in saved_rows:
        owner_id = int(row["created_by_id"])
        canonical_by_owner.setdefault(
            owner_id, int(row["id"])
        )

    saved_messages = bind.execute(
        sa.select(
            messages.c.id,
            messages.c.sender_id,
            messages.c.conversation_id,
        )
        .select_from(
            messages.join(
                conversations,
                messages.c.conversation_id
                == conversations.c.id,
            )
        )
        .where(conversations.c.type == "saved")
        .order_by(messages.c.id.asc())
    ).mappings().all()

    for row in saved_messages:
        sender_id = int(row["sender_id"])
        if sender_id in canonical_by_owner:
            continue
        result = bind.execute(
            sa.insert(conversations).values(
                type="saved",
                title="Избранное",
                created_by_id=sender_id,
            )
        )
        canonical_by_owner[sender_id] = int(
            result.inserted_primary_key[0]
        )

    owner_member_rows = bind.execute(
        sa.select(
            conversations.c.created_by_id,
            conversation_members.c.is_pinned,
            conversation_members.c.is_muted,
        )
        .select_from(
            conversation_members.join(
                conversations,
                conversation_members.c.conversation_id
                == conversations.c.id,
            )
        )
        .where(
            conversations.c.type == "saved",
            conversation_members.c.user_id
            == conversations.c.created_by_id,
        )
    ).mappings().all()

    pinned_by_owner: dict[int, bool] = {}
    muted_by_owner: dict[int, bool] = {}
    for row in owner_member_rows:
        owner_id = int(row["created_by_id"])
        pinned_by_owner[owner_id] = (
            pinned_by_owner.get(owner_id, False)
            or bool(row["is_pinned"])
        )
        muted_by_owner[owner_id] = (
            muted_by_owner.get(owner_id, False)
            or bool(row["is_muted"])
        )

    for owner_id, conv_id in canonical_by_owner.items():
        bind.execute(
            sa.update(conversations)
            .where(conversations.c.id == conv_id)
            .values(
                type="saved",
                title="Избранное",
                created_by_id=owner_id,
            )
        )

    for row in saved_messages:
        target_conv_id = canonical_by_owner[
            int(row["sender_id"])
        ]
        current_conv_id = int(row["conversation_id"])
        if current_conv_id == target_conv_id:
            continue
        bind.execute(
            sa.update(messages)
            .where(messages.c.id == int(row["id"]))
            .values(conversation_id=target_conv_id)
        )

    saved_message_locations = bind.execute(
        sa.select(
            messages.c.id,
            messages.c.conversation_id,
            messages.c.reply_to_id,
        )
        .select_from(
            messages.join(
                conversations,
                messages.c.conversation_id
                == conversations.c.id,
            )
        )
        .where(conversations.c.type == "saved")
    ).mappings().all()
    conversation_by_message = {
        int(row["id"]): int(row["conversation_id"])
        for row in saved_message_locations
    }
    for row in saved_message_locations:
        reply_to_id = row["reply_to_id"]
        if reply_to_id is None:
            continue
        if conversation_by_message.get(
            int(reply_to_id)
        ) == int(row["conversation_id"]):
            continue
        bind.execute(
            sa.update(messages)
            .where(messages.c.id == int(row["id"]))
            .values(reply_to_id=None)
        )

    saved_conv_ids = bind.execute(
        sa.select(conversations.c.id).where(
            conversations.c.type == "saved"
        )
    ).scalars().all()
    if saved_conv_ids:
        bind.execute(
            sa.delete(conversation_members).where(
                conversation_members.c.conversation_id.in_(
                    [int(conv_id) for conv_id in saved_conv_ids]
                )
            )
        )

    for owner_id, conv_id in canonical_by_owner.items():
        bind.execute(
            sa.insert(conversation_members).values(
                conversation_id=conv_id,
                user_id=owner_id,
                role="owner",
                is_pinned=pinned_by_owner.get(
                    owner_id, False
                ),
                is_muted=muted_by_owner.get(
                    owner_id, False
                ),
                last_read_message_id=None,
            )
        )

    canonical_ids = list(canonical_by_owner.values())
    bind.execute(
        sa.delete(conversations).where(
            conversations.c.type == "saved",
            conversations.c.id.notin_(canonical_ids),
        )
    )

    op.create_index(
        "ux_saved_conversations_owner",
        "conversations",
        ["created_by_id"],
        unique=True,
        sqlite_where=sa.text("type = 'saved'"),
        postgresql_where=sa.text("type = 'saved'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_saved_conversations_owner",
        table_name="conversations",
    )
