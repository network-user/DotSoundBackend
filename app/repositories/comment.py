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

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, **kwargs: Any) -> TrackComment:
        c = TrackComment(**kwargs)
        self._s.add(c)
        await self._s.flush()
        await self._s.refresh(c)
        return c

    async def get_by_id(self, comment_id: int) -> TrackComment | None:
        return await self._s.get(TrackComment, comment_id)

    async def get_root_comment_for_focus(
        self,
        track_ids: list[int],
        user_id: int,
        focus_comment_id: int,
    ) -> TrackComment | None:
        cur = await self.get_by_id(focus_comment_id)
        if not cur or cur.track_id not in track_ids:
            return None
        if cur.is_deleted or cur.is_hidden_by_author:
            return None
        while cur.parent_id is not None:
            parent = await self.get_by_id(cur.parent_id)
            if (
                not parent
                or parent.track_id not in track_ids
                or parent.is_deleted
                or parent.is_hidden_by_author
            ):
                return None
            cur = parent
        root = cur
        hid_row = await self._s.execute(
            select(CommentHide.comment_id)
            .where(
                CommentHide.comment_id == root.id,
                CommentHide.user_id == user_id,
            )
            .limit(1)
        )
        if hid_row.scalar_one_or_none() is not None:
            return None
        return root

    def _hidden_subquery(self, user_id: int) -> Any:
        return select(CommentHide.comment_id).where(
            CommentHide.user_id == user_id
        )

    def _reply_visibility(self, user_id: int) -> Any:
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
            TrackComment.is_hidden_by_author.is_(False),
            TrackComment.id.notin_(hid),
        )
        q = select(TrackComment).where(*cond)
        if cursor:
            q = q.where(TrackComment.id < cursor)
        q = q.order_by(
            TrackComment.is_pinned.desc(),
            TrackComment.created_at.desc(),
            TrackComment.id.desc(),
        ).limit(limit)
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def list_root_comments_for_tracks(
        self,
        track_ids: list[int],
        user_id: int,
        cursor: int | None,
        limit: int,
    ) -> list[TrackComment]:
        if not track_ids:
            return []
        hid = self._hidden_subquery(user_id)
        cond = (
            TrackComment.track_id.in_(track_ids),
            TrackComment.parent_id.is_(None),
            TrackComment.is_deleted.is_(False),
            TrackComment.is_hidden_by_author.is_(False),
            TrackComment.id.notin_(hid),
        )
        q = select(TrackComment).where(*cond)
        if cursor:
            q = q.where(TrackComment.id < cursor)
        q = q.order_by(
            TrackComment.is_pinned.desc(),
            TrackComment.created_at.desc(),
            TrackComment.id.desc(),
        ).limit(limit)
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
                TrackComment.track_id == track_id,
                TrackComment.parent_id.in_(parent_ids),
                TrackComment.is_deleted.is_(False),
                TrackComment.is_hidden_by_author.is_(False),
                TrackComment.id.notin_(hid),
                self._reply_visibility(user_id),
            )
            .order_by(TrackComment.created_at.asc())
        )
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def list_replies_for_parents_tracks(
        self,
        track_ids: list[int],
        parent_ids: list[int],
        user_id: int,
    ) -> list[TrackComment]:
        if not parent_ids or not track_ids:
            return []
        hid = self._hidden_subquery(user_id)
        q = (
            select(TrackComment)
            .where(
                TrackComment.track_id.in_(track_ids),
                TrackComment.parent_id.in_(parent_ids),
                TrackComment.is_deleted.is_(False),
                TrackComment.is_hidden_by_author.is_(False),
                TrackComment.id.notin_(hid),
                self._reply_visibility(user_id),
            )
            .order_by(TrackComment.created_at.asc())
        )
        rows = await self._s.execute(q)
        return list(rows.scalars().all())

    async def subtree_ids(self, comment_id: int) -> list[int]:
        root = await self.get_by_id(comment_id)
        if not root:
            return []
        ids = [comment_id]
        frontier = [comment_id]
        while frontier:
            r = await self._s.execute(
                select(TrackComment.id).where(
                    TrackComment.parent_id.in_(frontier)
                )
            )
            nxt = [row[0] for row in r.all()]
            if not nxt:
                break
            ids.extend(nxt)
            frontier = nxt
        return ids

    async def soft_delete_comment_chain(self, comment_id: int) -> list[int]:
        ids = await self.subtree_ids(comment_id)
        if not ids:
            return []
        for i in ids:
            row = await self.get_by_id(i)
            if row:
                row.is_deleted = True
        await self._s.flush()
        return ids

    async def hide_for_all_chain(self, comment_id: int) -> None:
        ids = await self.subtree_ids(comment_id)
        if not ids:
            return
        for i in ids:
            row = await self.get_by_id(i)
            if row:
                row.is_hidden_by_author = True
        await self._s.flush()

    async def soft_delete(self, comment_id: int) -> None:
        await self.soft_delete_comment_chain(comment_id)

    async def set_pinned(
        self,
        track_id: int,
        comment_id: int,
        pinned: bool,
    ) -> None:
        if pinned:
            rows = await self._s.execute(
                select(TrackComment).where(
                    TrackComment.track_id == track_id,
                    TrackComment.is_pinned.is_(True),
                )
            )
            for existing in rows.scalars().all():
                existing.is_pinned = False

        c = await self.get_by_id(comment_id)
        if c:
            c.is_pinned = pinned
            await self._s.flush()

    async def hide_for_all(self, comment_id: int) -> None:
        await self.hide_for_all_chain(comment_id)

    async def hide_for_user(self, comment_id: int, user_id: int) -> None:
        h = CommentHide(
            comment_id=comment_id,
            user_id=user_id,
        )
        self._s.add(h)
        await self._s.flush()

    async def get_vote(
        self,
        comment_id: int,
        user_id: int,
    ) -> CommentVote | None:
        return await self._s.get(CommentVote, (comment_id, user_id))

    async def vote(
        self,
        comment_id: int,
        user_id: int,
        is_like: bool,
    ) -> None:
        existing = await self.get_vote(comment_id, user_id)
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

    async def remove_vote(self, comment_id: int, user_id: int) -> None:
        await self._s.execute(
            delete(CommentVote).where(
                and_(
                    CommentVote.comment_id == comment_id,
                    CommentVote.user_id == user_id,
                )
            )
        )
        await self._s.flush()

    async def get_vote_counts(self, comment_id: int) -> tuple[int, int]:
        likes = await self._s.scalar(
            select(func.count()).where(
                CommentVote.comment_id == comment_id,
                CommentVote.is_like.is_(True),
            )
        )
        dislikes = await self._s.scalar(
            select(func.count()).where(
                CommentVote.comment_id == comment_id,
                CommentVote.is_like.is_(False),
            )
        )
        return likes or 0, dislikes or 0

    async def get_vote_counts_batch(
        self, comment_ids: list[int]
    ) -> dict[int, tuple[int, int]]:
        if not comment_ids:
            return {}
        rows = (
            await self._s.execute(
                select(
                    CommentVote.comment_id,
                    CommentVote.is_like,
                    func.count(),
                )
                .where(CommentVote.comment_id.in_(comment_ids))
                .group_by(
                    CommentVote.comment_id, CommentVote.is_like
                )
            )
        ).all()
        likes_map: dict[int, int] = {}
        dislikes_map: dict[int, int] = {}
        for cid, is_like, cnt in rows:
            target = likes_map if is_like else dislikes_map
            target[int(cid)] = int(cnt)
        return {
            cid: (likes_map.get(cid, 0), dislikes_map.get(cid, 0))
            for cid in comment_ids
        }
