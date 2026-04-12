from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import (
    CommentHide,
    CommentVote,
    TrackComment,
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class CommentRepository:
    def __init__(
        self, session: AsyncSession
    ) -> None:
        self._s = session

    async def create(
        self, **kwargs: Any
    ) -> TrackComment:
        c = TrackComment(**kwargs)
        self._s.add(c)
        await self._s.flush()
        await self._s.refresh(c)
        return c

    async def get_by_id(
        self, comment_id: int
    ) -> TrackComment | None:
        return await self._s.get(
            TrackComment, comment_id
        )

    async def list_comments(
        self,
        track_id: int,
        user_id: int,
        cursor: int | None = None,
        limit: int = 20,
    ) -> list[TrackComment]:
        hidden_ids = select(
            CommentHide.comment_id
        ).where(CommentHide.user_id == user_id)

        q = (
            select(TrackComment)
            .where(
                TrackComment.track_id == track_id,
                TrackComment.is_deleted.is_(False),
                TrackComment.is_hidden_by_author.is_(
                    False
                ),
                TrackComment.id.notin_(hidden_ids),
            )
            .order_by(
                TrackComment.is_pinned.desc(),
                TrackComment.created_at.desc(),
            )
            .limit(limit)
        )
        if cursor:
            q = q.where(TrackComment.id < cursor)
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def soft_delete(
        self, comment_id: int
    ) -> None:
        c = await self.get_by_id(comment_id)
        if c:
            c.is_deleted = True
            await self._s.flush()

    async def set_pinned(
        self,
        track_id: int,
        comment_id: int,
        pinned: bool,
    ) -> None:
        if pinned:
            await self._s.execute(
                select(TrackComment)
                .where(
                    TrackComment.track_id
                    == track_id,
                    TrackComment.is_pinned.is_(True),
                )
                .execution_options(
                    synchronize_session="fetch"
                )
            )
            rows = await self._s.execute(
                select(TrackComment).where(
                    TrackComment.track_id
                    == track_id,
                    TrackComment.is_pinned.is_(True),
                )
            )
            for existing in rows.scalars().all():
                existing.is_pinned = False

        c = await self.get_by_id(comment_id)
        if c:
            c.is_pinned = pinned
            await self._s.flush()

    async def hide_for_all(
        self, comment_id: int
    ) -> None:
        c = await self.get_by_id(comment_id)
        if c:
            c.is_hidden_by_author = True
            await self._s.flush()

    async def hide_for_user(
        self, comment_id: int, user_id: int
    ) -> None:
        h = CommentHide(
            comment_id=comment_id,
            user_id=user_id,
        )
        self._s.add(h)
        await self._s.flush()

    async def vote(
        self,
        comment_id: int,
        user_id: int,
        is_like: bool,
    ) -> None:
        existing = await self._s.get(
            CommentVote, (comment_id, user_id)
        )
        if existing:
            existing.is_like = is_like
        else:
            v = CommentVote(
                comment_id=comment_id,
                user_id=user_id,
                is_like=is_like,
            )
            self._s.add(v)
        await self._s.flush()

    async def remove_vote(
        self, comment_id: int, user_id: int
    ) -> None:
        await self._s.execute(
            delete(CommentVote).where(
                and_(
                    CommentVote.comment_id
                    == comment_id,
                    CommentVote.user_id == user_id,
                )
            )
        )
        await self._s.flush()

    async def get_vote_counts(
        self, comment_id: int
    ) -> tuple[int, int]:
        likes = await self._s.scalar(
            select(func.count()).where(
                CommentVote.comment_id
                == comment_id,
                CommentVote.is_like.is_(True),
            )
        )
        dislikes = await self._s.scalar(
            select(func.count()).where(
                CommentVote.comment_id
                == comment_id,
                CommentVote.is_like.is_(False),
            )
        )
        return likes or 0, dislikes or 0
