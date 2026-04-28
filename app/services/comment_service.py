from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ws_manager import ws_manager
from app.models.track import Track
from app.models.user import User
from app.repositories.block import BlockRepository
from app.repositories.comment import (
    CommentRepository,
)
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


class CommentService:
    def __init__(
        self, session: AsyncSession
    ) -> None:
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

    def _raise_unless_comments_allowed(
        self, track: Track | None
    ) -> None:
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        if not track.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Comments not available for private tracks"
                ),
            )
        if not track.comments_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Comments disabled",
            )

    async def add_comment(
        self,
        track_id: int,
        user_id: int,
        text: str,
    ) -> dict[str, Any]:
        track = await self._session.get(
            Track, track_id
        )
        self._raise_unless_comments_allowed(track)
        assert track is not None
        if track.uploaded_by_id:
            if await self._block_repo.is_blocked(
                track.uploaded_by_id, user_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Blocked by track owner",
                )

        c = await self._repo.create(
            track_id=track_id,
            user_id=user_id,
            text=text,
        )
        logger.info(
            "comment_added",
            comment_id=c.id,
            track_id=track_id,
        )
        author = await self._user_repo.get_by_id(
            user_id
        )
        author_label = self._author_label(author)
        result = {
            "id": c.id,
            "track_id": track_id,
            "user_id": user_id,
            "text": text,
            "is_pinned": False,
            "created_at": c.created_at.isoformat(),
            "likes": 0,
            "dislikes": 0,
            "author_label": author_label,
        }
        await ws_manager.broadcast_to_online(
            {"event": "comment.new", **result}
        )
        return result

    async def get_comments(
        self,
        track_id: int,
        user_id: int,
        cursor: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        track = await self._session.get(
            Track, track_id
        )
        self._raise_unless_comments_allowed(track)
        comments = await self._repo.list_comments(
            track_id, user_id, cursor, limit
        )
        author_ids = [c.user_id for c in comments]
        users = await self._user_repo.get_by_ids(
            author_ids
        )
        result: list[dict[str, Any]] = []
        for c in comments:
            likes, dislikes = (
                await self._repo.get_vote_counts(
                    c.id
                )
            )
            au = users.get(c.user_id)
            result.append(
                {
                    "id": c.id,
                    "track_id": c.track_id,
                    "user_id": c.user_id,
                    "text": c.text,
                    "is_pinned": c.is_pinned,
                    "created_at": c.created_at.isoformat(),
                    "likes": likes,
                    "dislikes": dislikes,
                    "author_label": self._author_label(au),
                }
            )
        return result

    async def delete_comment(
        self, comment_id: int, user_id: int
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(
            Track, c.track_id
        )
        is_owner = (
            track
            and track.uploaded_by_id == user_id
        )
        if c.user_id != user_id and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed",
            )
        await self._repo.soft_delete(comment_id)
        await ws_manager.broadcast_to_online(
            {
                "event": "comment.deleted",
                "comment_id": comment_id,
                "track_id": c.track_id,
            }
        )

    async def pin_comment(
        self, comment_id: int, user_id: int
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(
            Track, c.track_id
        )
        self._raise_unless_comments_allowed(track)
        await self._ensure_track_owner(
            c.track_id, user_id
        )
        await self._repo.set_pinned(
            c.track_id, comment_id, True
        )

    async def unpin_comment(
        self, comment_id: int, user_id: int
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(
            Track, c.track_id
        )
        self._raise_unless_comments_allowed(track)
        await self._ensure_track_owner(
            c.track_id, user_id
        )
        await self._repo.set_pinned(
            c.track_id, comment_id, False
        )

    async def hide_for_all(
        self, comment_id: int, user_id: int
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(
            Track, c.track_id
        )
        self._raise_unless_comments_allowed(track)
        await self._ensure_track_owner(
            c.track_id, user_id
        )
        await self._repo.hide_for_all(comment_id)

    async def hide_for_self(
        self, comment_id: int, user_id: int
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(
            Track, c.track_id
        )
        self._raise_unless_comments_allowed(track)
        await self._repo.hide_for_user(
            comment_id, user_id
        )

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
        track = await self._session.get(
            Track, c.track_id
        )
        self._raise_unless_comments_allowed(track)
        await self._repo.vote(
            comment_id, user_id, is_like
        )

    async def remove_vote(
        self, comment_id: int, user_id: int
    ) -> None:
        c = await self._repo.get_by_id(comment_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        track = await self._session.get(
            Track, c.track_id
        )
        self._raise_unless_comments_allowed(track)
        await self._repo.remove_vote(
            comment_id, user_id
        )

    async def _ensure_track_owner(
        self, track_id: int, user_id: int
    ) -> None:
        track = await self._session.get(
            Track, track_id
        )
        if (
            not track
            or track.uploaded_by_id != user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only track owner can do this",
            )
