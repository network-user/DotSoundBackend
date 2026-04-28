from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.services.comment_service import (
    CommentService,
)

pytestmark = pytest.mark.anyio

_WS = "app.core.ws_manager.ws_manager"


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1000,
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_track(
    session: AsyncSession,
    owner: User,
    comments_enabled: bool = True,
    is_public: bool = True,
) -> Track:
    track = Track(
        title="T",
        file_key="k",
        uploaded_by_id=owner.id,
        comments_enabled=comments_enabled,
        is_public=is_public,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_add_comment(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(session, user)

    svc = CommentService(session)
    result = await svc.add_comment(
        track.id, user.id, "Great track!"
    )

    assert result["text"] == "Great track!"
    assert result["track_id"] == track.id
    assert "author_label" in result
    assert result["author_label"]
    mock_ws.assert_awaited_once()


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_add_comment_author_label_prefers_display_name(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    user.display_name = "Studio Artist"
    await session.flush()
    track = await _make_track(session, user)

    svc = CommentService(session)
    result = await svc.add_comment(
        track.id, user.id, "Hi"
    )

    assert result["author_label"] == "Studio Artist"


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_add_comment_track_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = CommentService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.add_comment(
            9999, user.id, "text"
        )

    assert exc.value.status_code == 404


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_add_comment_disabled(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(
        session, user, comments_enabled=False
    )

    svc = CommentService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.add_comment(
            track.id, user.id, "text"
        )

    assert exc.value.status_code == 403


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_add_comment_private_track(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(
        session, user, is_public=False
    )

    svc = CommentService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.add_comment(
            track.id, user.id, "text"
        )

    assert exc.value.status_code == 403


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_get_comments_private_track(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(session, user)
    svc = CommentService(session)
    await svc.add_comment(track.id, user.id, "x")
    track.is_public = False
    await session.flush()

    with pytest.raises(HTTPException) as exc:
        await svc.get_comments(track.id, user.id)

    assert exc.value.status_code == 403


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_delete_comment_by_author(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(session, user)

    svc = CommentService(session)
    result = await svc.add_comment(
        track.id, user.id, "to delete"
    )

    await svc.delete_comment(
        result["id"], user.id
    )


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_delete_comment_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = CommentService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.delete_comment(9999, 1)

    assert exc.value.status_code == 404


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_vote_comment(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    track = await _make_track(session, user)
    svc = CommentService(session)
    c = await svc.add_comment(
        track.id, user.id, "text"
    )

    await svc.vote(c["id"], user.id, True)


@patch(f"{_WS}.broadcast_to_online", new_callable=AsyncMock)
async def test_vote_comment_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = CommentService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.vote(9999, 1, True)

    assert exc.value.status_code == 404
