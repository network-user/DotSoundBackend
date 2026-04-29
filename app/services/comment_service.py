from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ws_manager import ws_manager
from app.models.comment import CommentVote, TrackComment
from app.models.track import Track
from app.models.user import User
from app.repositories.block import BlockRepository
from app.repositories.comment import (
    CommentRepository,
)
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.playback_variant_service import PlaybackVariantService
from app.services.comment_notifications import (
    comment_like_copy,
    comment_reply_copy,
    truncate_preview,
)
from app.services.notification_service import (
    NotificationService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class CommentService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = CommentRepository(session)
        self._block_repo = BlockRepository(session)
        self._user_repo = UserRepository(session)
        self._session = session

    @staticmethod
    def _author_label(user: User | None) -> str:
        if not user:
            return ""
        dn = (user.display_name or "").strip()
        if dn:
            return dn
        un = (user.username or "").strip()
        if un:
            return un
        parts = [user.first_name]
        if user.last_name:
            parts.append(user.last_name)
        joined = " ".join(p for p in parts if p).strip()
        if joined:
            return joined
        return f"User #{user.id}"

    async def _storage_track(self, track: Track) -> Track:
        pvs = PlaybackVariantService(self._session)
        repo = TrackRepository(self._session)
        ids = await pvs.resolve_variant_track_ids(track)
        rows = await repo.get_by_ids_preserve_order(ids)
        active = [r for r in rows if r.is_active and r.is_public]
        if not active:
            return track
        return pvs.pick_primary_track(active)

    async def _variant_track_ids(self, track: Track) -> list[int]:
        pvs = PlaybackVariantService(self._session)
        return await pvs.resolve_variant_track_ids(track)

    def _raise_unless_comments_allowed(self, track: Track | None) -> None:
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        if not track.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("Comments not available for private tracks"),
            )
        if not track.comments_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Comments disabled",
            )

    async def _comment_dict(
        self,
        c: TrackComment,
        users: dict[int, User],
    ) -> dict[str, Any]:
        likes, dislikes = await self._repo.get_vote_counts(c.id)
        au = users.get(c.user_id)
        return {
            "id": c.id,
            "track_id": c.track_id,
            "user_id": c.user_id,
            "parent_id": c.parent_id,
            "text": c.text,
            "is_pinned": c.is_pinned,
            "created_at": c.created_at.isoformat(),
            "likes": likes,
            "dislikes": dislikes,
            "author_label": self._author_label(au),
        }

    async def _notify_comment_reply(
        self,
        *,
        track: Track,
        new_comment: TrackComment,
        text: str,
        actor: User | None,
        parent_author_id: int,
    ) -> None:
        if parent_author_id == new_comment.user_id:
            return
        if await self._block_repo.is_blocked(
            new_comment.user_id, parent_author_id
        ):
            return
        parent_user = await self._user_repo.get_by_id(parent_author_id)
        if not parent_user:
            return
        al = self._author_label(actor)
        title, body = comment_reply_copy(
            parent_user.locale,
            al,
            text,
            track.title,
        )
        notif = NotificationService(self._session)
        await notif.create(
            user_id=parent_author_id,
            ntype="comment_reply",
            title=title,
            body=body,
            data={
                "track_id": track.id,
                "comment_id": new_comment.id,
                "actor_user_id": new_comment.user_id,
                "actor_label": al,
                "preview": truncate_preview(text),
                "track_title": (track.title or "").strip(),
            },
        )

    async def _notify_comment_liked(
        self,
        *,
        track: Track,
        comment: TrackComment,
        actor_id: int,
        actor: User | None,
    ) -> None:
        owner_id = comment.user_id
        if owner_id == actor_id:
            return
        if comment.is_deleted or comment.is_hidden_by_author:
            return
        if await self._block_repo.is_blocked(actor_id, owner_id):
            return
        owner = await self._user_repo.get_by_id(owner_id)
        if not owner:
            return
        al = self._author_label(actor)
        title, body = comment_like_copy(
            owner.locale,
            al,
            track.title,
        )
        notif = NotificationService(self._session)
        await notif.create(
            user_id=owner_id,
            ntype="comment_like",
            title=title,
            body=body,
            data={
                "track_id": track.id,
                "comment_id": comment.id,
                "actor_user_id": actor_id,
                "actor_label": al,
                "track_title": (track.title or "").strip(),
            },
        )

    async def add_comment(
        self,
        track_id: int,
        user_id: int,
        text: str,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        track = await self._session.get(Track, track_id)
        self._raise_unless_comments_allowed(track)
        assert track is not None
        storage = await self._storage_track(track)
        variant_ids = await self._variant_track_ids(track)
        if storage.uploaded_by_id and await self._block_repo.is_blocked(
            storage.uploaded_by_id, user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Blocked by track owner",
            )

        parent_row: TrackComment | None = None
        if parent_id is not None:
            parent_row = await self._repo.get_by_id(parent_id)
            if not parent_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent comment not found",
                )
            if parent_row.track_id not in variant_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid parent comment",
                )
            if parent_row.is_deleted or parent_row.is_hidden_by_author:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reply to this comment",
                )

        c = await self._repo.create(
            track_id=storage.id,
            user_id=user_id,
            text=text,
            parent_id=parent_id,
        )
        logger.info(
            "comment_added",
            comment_id=c.id,
            track_id=storage.id,
            parent_id=parent_id,
        )
        author = await self._user_repo.get_by_id(user_id)
        author_label = self._author_label(author)
        result = {
            "id": c.id,
            "track_id": storage.id,
            "user_id": user_id,
            "parent_id": parent_id,
            "text": text,
            "is_pinned": False,
            "created_at": c.created_at.isoformat(),
            "likes": 0,
            "dislikes": 0,
            "author_label": author_label,
            "replies": [],
        }
        await ws_manager.broadcast_to_online(
            {"event": "comment.new", **result}
        )
        if parent_id is not None and parent_row is not None:
            await self._notify_comment_reply(
                track=storage,
                new_comment=c,
                text=text,
                actor=author,
                parent_author_id=parent_row.user_id,
            )
        return result

    async def get_comments(
        self,
        track_id: int,
        user_id: int,
        cursor: int | None = None,
        limit: int = 20,
        focus_comment_id: int | None = None,
    ) -> list[dict[str, Any]]:
        track = await self._session.get(Track, track_id)
        self._raise_unless_comments_allowed(track)
        assert track is not None
        variant_ids = await self._variant_track_ids(track)
        roots = await self._repo.list_root_comments_for_tracks(
            variant_ids, user_id, cursor, limit
        )
        extra_root: TrackComment | None = None
        if focus_comment_id is not None:
            extra_root = await self._repo.get_root_comment_for_focus(
                variant_ids,
                user_id,
                focus_comment_id,
            )
            if extra_root is not None:
                ids = {r.id for r in roots}
                if extra_root.id not in ids:
                    roots = [extra_root, *roots]
                    roots.sort(
                        key=lambda r: (
                            r.is_pinned,
                            r.created_at,
                        ),
                        reverse=True,
                    )
        if not roots:
            return []
        all_flat: list[TrackComment] = []
        frontier = [r.id for r in roots]
        while frontier:
            batch = await self._repo.list_replies_for_parents_tracks(
                variant_ids, frontier, user_id
            )
            if not batch:
                break
            all_flat.extend(batch)
            frontier = [b.id for b in batch]

        by_parent: dict[int, list[TrackComment]] = {}
        for node in all_flat:
            by_parent.setdefault(node.parent_id, []).append(node)
        for pid in by_parent:
            by_parent[pid].sort(
                key=lambda x: x.created_at,
            )

        uid_set: set[int] = set()
        for x in roots:
            uid_set.add(x.user_id)
        for x in all_flat:
            uid_set.add(x.user_id)
        users = await self._user_repo.get_by_ids(list(uid_set))

        async def branch(
            node: TrackComment,
        ) -> dict[str, Any]:
            d = await self._comment_dict(node, users)
            kids = by_parent.get(node.id, [])
            d["replies"] = [await branch(ch) for ch in kids]
            return d

        out: list[dict[str, Any]] = []
        for root in roots:
            out.append(await branch(root))
        return out

    async def delete_comment(self, comment_id: int, user_id: int) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(Track, c.track_id)
        is_owner = track and track.uploaded_by_id == user_id
        if c.user_id != user_id and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed",
            )
        tid = c.track_id
        deleted_ids = await self._repo.soft_delete_comment_chain(comment_id)
        for did in deleted_ids:
            await ws_manager.broadcast_to_online(
                {
                    "event": "comment.deleted",
                    "comment_id": did,
                    "track_id": tid,
                }
            )

    async def pin_comment(self, comment_id: int, user_id: int) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        if c.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only pin top-level comments",
            )
        track = await self._session.get(Track, c.track_id)
        self._raise_unless_comments_allowed(track)
        await self._ensure_track_owner(c.track_id, user_id)
        await self._repo.set_pinned(c.track_id, comment_id, True)

    async def unpin_comment(self, comment_id: int, user_id: int) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        if c.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only unpin top-level comments",
            )
        track = await self._session.get(Track, c.track_id)
        self._raise_unless_comments_allowed(track)
        await self._ensure_track_owner(c.track_id, user_id)
        await self._repo.set_pinned(c.track_id, comment_id, False)

    async def hide_for_all(self, comment_id: int, user_id: int) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(Track, c.track_id)
        self._raise_unless_comments_allowed(track)
        await self._ensure_track_owner(c.track_id, user_id)
        await self._repo.hide_for_all(comment_id)

    async def hide_for_self(self, comment_id: int, user_id: int) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(Track, c.track_id)
        self._raise_unless_comments_allowed(track)
        await self._repo.hide_for_user(comment_id, user_id)

    async def vote(
        self,
        comment_id: int,
        user_id: int,
        is_like: bool,
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(Track, c.track_id)
        self._raise_unless_comments_allowed(track)
        assert track is not None
        prev: CommentVote | None = await self._repo.get_vote(
            comment_id, user_id
        )
        await self._repo.vote(comment_id, user_id, is_like)
        became_like = is_like and (prev is None or not prev.is_like)
        if became_like:
            actor = await self._user_repo.get_by_id(user_id)
            await self._notify_comment_liked(
                track=track,
                comment=c,
                actor_id=user_id,
                actor=actor,
            )

    async def remove_vote(self, comment_id: int, user_id: int) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(Track, c.track_id)
        self._raise_unless_comments_allowed(track)
        await self._repo.remove_vote(comment_id, user_id)

    async def _ensure_track_owner(self, track_id: int, user_id: int) -> None:
        track = await self._session.get(Track, track_id)
        if not track or track.uploaded_by_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only track owner can do this",
            )
