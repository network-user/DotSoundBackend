from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.chat_service import ChatService
from app.services.message_service import (
    MessageService,
)

pytestmark = pytest.mark.anyio

_WS = "app.core.ws_manager.ws_manager"
_ENC = "app.services.message_service"


async def _make_user(
    session: AsyncSession,
    telegram_id: int,
) -> int:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user.id


async def _make_dm(
    session: AsyncSession,
    u1: int,
    u2: int,
) -> int:
    svc = ChatService(session)
    result = await svc.create_dm(u1, u2)
    return result["conversation"]["id"]


_ENC_RV = (b"enc", b"123456789012")


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_send_message(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1200)
    u2 = await _make_user(session, 1201)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "Hello"
    )

    assert result["content"] == "Hello"
    assert result["sender_id"] == u1


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_send_message_not_member(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1202)
    u2 = await _make_user(session, 1203)
    u3 = await _make_user(session, 1204)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.send_message(cid, u3, "Hi")

    assert exc.value.status_code == 403


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_get_messages(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1205)
    u2 = await _make_user(session, 1206)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "msg", broadcast=False
    )

    assert result["content"] == "msg"
    assert result["sender_id"] == u1
    assert result["conversation_id"] == cid


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
async def test_get_messages_not_member(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1207)
    u2 = await _make_user(session, 1208)
    u3 = await _make_user(session, 1209)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_messages(cid, u3)

    assert exc.value.status_code == 403


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_delete_message(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1210)
    u2 = await _make_user(session, 1211)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "del", broadcast=False
    )

    await svc.delete_message(result["id"], u1)


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
async def test_delete_message_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = MessageService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.delete_message(9999, 1)

    assert exc.value.status_code == 404


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
@patch(f"{_ENC}.decrypt_message", new_callable=AsyncMock, return_value="hello")
async def test_get_messages_success(
    mock_dec: AsyncMock,
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1220)
    u2 = await _make_user(session, 1221)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    await svc.send_message(
        cid, u1, "hello", broadcast=False
    )

    msgs = await svc.get_messages(cid, u1)

    assert len(msgs) >= 1
    assert msgs[0]["sender_id"] == u1


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_add_reaction(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1230)
    u2 = await _make_user(session, 1231)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "react me", broadcast=False
    )

    await svc.add_reaction(
        result["id"], u1, "like"
    )


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
async def test_add_reaction_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = MessageService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.add_reaction(
            9999, 1, "like"
        )

    assert exc.value.status_code == 404


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_remove_reaction(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1240)
    u2 = await _make_user(session, 1241)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "remove me", broadcast=False
    )
    await svc.add_reaction(
        result["id"], u1, "like"
    )
    await svc.remove_reaction(
        result["id"], u1, "like"
    )


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
async def test_remove_reaction_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = MessageService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.remove_reaction(
            9999, 1, "like"
        )

    assert exc.value.status_code == 404


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_mark_as_read(
    mock_enc: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1250)
    u2 = await _make_user(session, 1251)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "read me", broadcast=False
    )

    await svc.mark_as_read(
        cid, u2, result["id"]
    )


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
async def test_mark_as_read_not_member(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1260)
    u2 = await _make_user(session, 1261)
    u3 = await _make_user(session, 1262)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)

    await svc.mark_as_read(cid, u3, 1)


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
@patch(f"{_ENC}.decrypt_message", new_callable=AsyncMock, return_value="hi")
@patch(f"{_ENC}.encrypt_message", new_callable=AsyncMock, return_value=_ENC_RV)
async def test_broadcast_message(
    mock_enc: AsyncMock,
    mock_dec: AsyncMock,
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1270)
    u2 = await _make_user(session, 1271)
    cid = await _make_dm(session, u1, u2)

    svc = MessageService(session)
    result = await svc.send_message(
        cid, u1, "hi", broadcast=False
    )

    await svc.broadcast_message(result["id"])

    mock_ws.assert_awaited()


@patch(f"{_WS}.send_to_conversation", new_callable=AsyncMock)
async def test_broadcast_message_not_found(
    mock_ws: AsyncMock,
    session: AsyncSession,
) -> None:
    svc = MessageService(session)

    await svc.broadcast_message(9999)
