import pytest
from pydantic import ValidationError

from app.schemas.chat import (
    AddMemberRequest,
    CommentRequest,
    CreateDMRequest,
    CreateGroupRequest,
    MarkReadRequest,
    ReactionRequest,
    ReadNotificationsRequest,
    SendMessageRequest,
    UnreadNotificationRequest,
    VoteRequest,
)


def test_create_dm_valid() -> None:
    req = CreateDMRequest(target_user_id=42)
    assert req.target_user_id == 42


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="missing"),
        pytest.param(
            {"target_user_id": "abc"},
            id="wrong_type",
        ),
    ],
)
def test_create_dm_invalid(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CreateDMRequest(**kwargs)


def test_create_group_valid() -> None:
    req = CreateGroupRequest(
        title="Group", member_ids=[1, 2, 3]
    )
    assert req.title == "Group"
    assert req.member_ids == [1, 2, 3]


def test_create_group_title_too_long() -> None:
    with pytest.raises(ValidationError):
        CreateGroupRequest(
            title="x" * 257, member_ids=[1]
        )


def test_create_group_title_max_length() -> None:
    req = CreateGroupRequest(
        title="x" * 256, member_ids=[]
    )
    assert len(req.title) == 256


def test_create_group_empty_members() -> None:
    req = CreateGroupRequest(
        title="G", member_ids=[]
    )
    assert req.member_ids == []


def test_create_group_missing_title() -> None:
    with pytest.raises(ValidationError):
        CreateGroupRequest(member_ids=[1])


def test_add_member_valid() -> None:
    req = AddMemberRequest(user_id=7)
    assert req.user_id == 7


def test_add_member_missing() -> None:
    with pytest.raises(ValidationError):
        AddMemberRequest()


def test_send_message_valid() -> None:
    req = SendMessageRequest(content="Hello!")
    assert req.content == "Hello!"
    assert req.type == "text"
    assert req.reply_to_id is None
    assert req.shared_track_id is None


def test_send_message_full() -> None:
    req = SendMessageRequest(
        content="Hi",
        type="track_share",
        reply_to_id=5,
        shared_track_id=10,
    )
    assert req.type == "track_share"
    assert req.reply_to_id == 5
    assert req.shared_track_id == 10


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("x" * 4097, id="too_long"),
    ],
)
def test_send_message_invalid_content(
    content: str,
) -> None:
    with pytest.raises(ValidationError):
        SendMessageRequest(content=content)


def test_send_message_content_max_length() -> None:
    req = SendMessageRequest(content="x" * 4096)
    assert len(req.content) == 4096


def test_send_message_missing_content() -> None:
    with pytest.raises(ValidationError):
        SendMessageRequest()


def test_reaction_request_valid() -> None:
    req = ReactionRequest(reaction_type="thumbs_up")
    assert req.reaction_type == "thumbs_up"


def test_reaction_request_too_long() -> None:
    with pytest.raises(ValidationError):
        ReactionRequest(reaction_type="x" * 31)


def test_reaction_request_max_length() -> None:
    req = ReactionRequest(reaction_type="x" * 30)
    assert len(req.reaction_type) == 30


def test_mark_read_valid() -> None:
    req = MarkReadRequest(message_id=99)
    assert req.message_id == 99


def test_mark_read_missing() -> None:
    with pytest.raises(ValidationError):
        MarkReadRequest()


@pytest.mark.parametrize(
    "is_like", [True, False],
)
def test_vote_request(is_like: bool) -> None:
    req = VoteRequest(is_like=is_like)
    assert req.is_like is is_like


def test_vote_request_missing() -> None:
    with pytest.raises(ValidationError):
        VoteRequest()


def test_comment_request_valid() -> None:
    req = CommentRequest(text="Great track!")
    assert req.text == "Great track!"


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty"),
        pytest.param("x" * 1001, id="too_long"),
    ],
)
def test_comment_request_invalid(
    text: str,
) -> None:
    with pytest.raises(ValidationError):
        CommentRequest(text=text)


def test_comment_request_min_length() -> None:
    req = CommentRequest(text="A")
    assert req.text == "A"


def test_comment_request_max_length() -> None:
    req = CommentRequest(text="x" * 1000)
    assert len(req.text) == 1000


def test_read_notifications_valid() -> None:
    req = ReadNotificationsRequest(
        notification_id=1
    )
    assert req.notification_id == 1


def test_read_notifications_missing() -> None:
    with pytest.raises(ValidationError):
        ReadNotificationsRequest()


def test_unread_notification_valid() -> None:
    req = UnreadNotificationRequest(
        notification_id=1
    )
    assert req.notification_id == 1
