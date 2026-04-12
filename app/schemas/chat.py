from __future__ import annotations

from pydantic import BaseModel


class CreateDMRequest(BaseModel):
    target_user_id: int


class CreateGroupRequest(BaseModel):
    title: str
    member_ids: list[int]


class AddMemberRequest(BaseModel):
    user_id: int


class SendMessageRequest(BaseModel):
    content: str
    type: str = "text"
    reply_to_id: int | None = None
    shared_track_id: int | None = None


class ReactionRequest(BaseModel):
    reaction_type: str


class MarkReadRequest(BaseModel):
    message_id: int


class VoteRequest(BaseModel):
    is_like: bool


class CommentRequest(BaseModel):
    text: str


class ReadNotificationsRequest(BaseModel):
    notification_id: int
