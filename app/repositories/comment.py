from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, delete, func, or_, select
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

    def _hidden_subquery(self, user_id: int) -> Any:
        return select(CommentHide.comment_id).where(
            CommentHide.user_id == user_id
        )

    def _reply_visibility(
        self, user_id: int
    ) -> Any:
        hid = self._hidden_subquery(user_id)
        return or_(
            TrackComment.parent_id.is_(None),
            TrackComment.parent_id.notin_(hid),
        )

    async def list_root_comments(
        self,
        track_id: int,
        user_id: int,
        cursor: int | None,
        limit: int,
    ) -> list[TrackComment]:
        hid = self._hidden_subquery(user_id)
        cond = (
            TrackComment.track_id == track_id,
            TrackComment.parent_id.is_(None),
            TrackComment.is_deleted.is_(False),
            TrackComment.is_hidden_by_author.is_(
                False
            ),
            TrackComment.id.notin_(hid),
        )
        q = select(TrackComment).where(*cond)
        if cursor:
            q = q.where(TrackComment.id < cursor)
        q = (
            q.order_by(
                TrackComment.is_pinned.desc(),
                TrackComment.created_at.desc(),
            ).limit(limit)
        )
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def list_replies_for_parents(
        self,
        track_id: int,
        parent_ids: list[int],
        user_id: int,
    ) -> list[TrackComment]:
        if not parent_ids:
            return []
        hid = self._hidden_subquery(user_id)
        q = (
            select(TrackComment)
            .where(
                TrackComment.track_id
                == track_id,
                TrackComment.parent_id.in_(
                    parent_ids
                ),
                TrackComment.is_deleted.is_(False),
                TrackComment.is_hidden_by_author.is_(
                    False
                ),
                TrackComment.id.notin_(hid),
                self._reply_visibility(user_id),
            )
            .order_by(TrackComment.created_at.asc())
        )
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def soft_delete_comment_chain(
        self, comment_id: int
    ) -> list[int]:
        c = await self.get_by_id(comment_id)
        if not c:
            return []
        ids: list[int] = [comment_id]
        if c.parent_id is None:
            r = await self._s.execute(
                select(TrackComment.id).where(
                    TrackComment.parent_id
                    == comment_id
                )
            )
            ids.extend(row[0] for row in r.all())
        for i in ids:
            row = await self.get_by_id(i)
            if row:
                row.is_deleted = True
        await self._s.flush()
        return ids

    async def hide_for_all_chain(
        self, comment_id: int
    ) -> None:
        c = await self.get_by_id(comment_id)
        if not c:
            return
        ids: list[int] = [comment_id]
        if c.parent_id is None:
            r = await self._s.execute(
                select(TrackComment.id).where(
                    TrackComment.parent_id
                    == comment_id
                )
            )
            ids.extend(row[0] for row in r.all())
        for i in ids:
            row = await self.get_by_id(i)
            if row:
                row.is_hidden_by_author = True
        await self._s.flush()

    async def soft_delete(
        self, comment_id: int
    ) -> None:
        await self.soft_delete_comment_chain(
            comment_id
        )

    async def set_pinned(
        self,
        track_id: int,
        comment_id: int,
        pinned: bool,
    ) -> None:
        if pinned:
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
        await self.hide_for_all_chain(comment_id)

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
