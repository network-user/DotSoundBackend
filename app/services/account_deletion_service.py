"""User account hard-delete pipeline.

Runs once a day from the Taskiq scheduler (see
``alembic 0078_user_hard_delete_anonymize_fks``). Picks up users whose
``deleted_at`` has crossed the grace period defined in PrivateCore
(``account_deletion_policy.GRACE_PERIOD_DAYS``) and removes them.

Anonymization model (per ``AGENTS.md``):
    * messages, track_comments  -> SET NULL via FK (see migration 0078)
    * tracks.uploaded_by_id     -> SET NULL via existing FK (kept;
      other users may still have it in their library)
    * artists.owner_user_id     -> SET NULL via existing FK
    * likes/dislikes/eq/follows/library/etc. -> CASCADE via existing FK
    * S3 avatar -> deleted explicitly here
    * users row -> deleted (cascades into the rest)

The actual list of FK actions is defined in the schema; this service
is a thin orchestrator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.user import User
from app.repositories.user import UserRepository
from dotsound_private_core.services.account_deletion_policy import (
    HARD_DELETE_BATCH_LIMIT,
    hard_delete_cutoff,
    should_hard_delete,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AccountDeletionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UserRepository(session)

    async def hard_delete_expired_users(
        self,
        *,
        now: datetime | None = None,
        batch_limit: int | None = None,
    ) -> dict[str, Any]:
        """Hard-delete every user whose grace period has expired.

        Returns a structured summary suitable for structured logs.
        """
        cutoff = hard_delete_cutoff(now or datetime.now(UTC))
        limit = batch_limit or HARD_DELETE_BATCH_LIMIT

        candidates = await self._repo.list_hard_delete_candidates(
            cutoff=cutoff, limit=limit
        )
        deleted: list[int] = []
        skipped: list[int] = []
        avatar_keys_freed: list[str] = []

        for user in candidates:
            if user.deleted_at is None or not should_hard_delete(
                user.deleted_at
            ):
                skipped.append(user.id)
                continue

            avatar_key = user.avatar_key
            user_id = user.id
            try:
                await self._repo.hard_delete(user_id)
            except Exception:
                logger.exception(
                    "account_hard_delete_db_failed",
                    user_id=user_id,
                )
                skipped.append(user_id)
                continue

            deleted.append(user_id)
            if avatar_key:
                ok = await self._best_effort_delete_avatar(
                    user_id, avatar_key
                )
                if ok:
                    avatar_keys_freed.append(avatar_key)

        summary = {
            "scanned": len(candidates),
            "deleted": len(deleted),
            "skipped": len(skipped),
            "avatar_keys_freed": len(avatar_keys_freed),
            "cutoff": cutoff.isoformat(),
        }
        logger.info("account_hard_delete_summary", **summary)
        return summary

    async def _best_effort_delete_avatar(
        self, user_id: int, avatar_key: str
    ) -> bool:
        try:
            await s3.delete_object(avatar_key)
        except Exception:
            logger.warning(
                "account_hard_delete_avatar_cleanup_failed",
                user_id=user_id,
                avatar_key=avatar_key,
                exc_info=True,
            )
            return False
        return True

    @staticmethod
    def is_eligible(user: User) -> bool:
        if user.deleted_at is None:
            return False
        return should_hard_delete(user.deleted_at)
