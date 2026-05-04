from __future__ import annotations

from pydantic import BaseModel, Field


class CreateDMRequest(BaseModel):
    target_user_id: int


class CreateGroupRequest(BaseModel):
    title: str = Field(max_length=256)
    member_ids: list[int]


class AddMemberRequest(BaseModel):
    user_id: int


class SendMessageRequest(BaseModel):
    content: str = Field(max_length=4096)
    type: str = "text"
    reply_to_id: int | None = None
    shared_track_id: int | None = None
    shared_album_id: int | None = None
    shared_playlist_id: int | None = None


class ReactionRequest(BaseModel):
    reaction_type: str = Field(max_length=30)


class MarkReadRequest(BaseModel):
    message_id: int


class VoteRequest(BaseModel):
    is_like: bool


class CommentRequest(BaseModel):
    text: str = Field(
        min_length=1, max_length=1000
    )
    parent_id: int | None = None


class ReadNotificationsRequest(BaseModel):
    notification_id: int


class UnreadNotificationRequest(BaseModel):
    notification_id: int
