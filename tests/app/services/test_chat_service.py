import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.chat_service import ChatService

pytestmark = pytest.mark.anyio


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


async def test_create_dm(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1100)
    u2 = await _make_user(session, 1101)

    svc = ChatService(session)
    result = await svc.create_dm(u1, u2)

    assert "conversation" in result
    assert result["conversation"]["type"] == "dm"


async def test_create_dm_self_raises(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1102)
    svc = ChatService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.create_dm(u1, u1)

    assert exc.value.status_code == 400


async def test_create_dm_returns_existing(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1103)
    u2 = await _make_user(session, 1104)

    svc = ChatService(session)
    r1 = await svc.create_dm(u1, u2)
    r2 = await svc.create_dm(u1, u2)

    assert (
        r1["conversation"]["id"]
        == r2["conversation"]["id"]
    )


async def test_create_group(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1105)
    u2 = await _make_user(session, 1106)

    svc = ChatService(session)
    result = await svc.create_group(
        u1, "Group", [u2]
    )

    assert (
        result["conversation"]["type"] == "group"
    )


async def test_list_chats(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1107)
    u2 = await _make_user(session, 1108)

    svc = ChatService(session)
    await svc.create_dm(u1, u2)

    chats = await svc.list_chats(u1)

    assert len(chats) >= 1


async def test_get_or_create_saved(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1109)
    svc = ChatService(session)

    result = await svc.get_or_create_saved(u1)

    assert (
        result["conversation"]["type"] == "saved"
    )


async def test_get_or_create_saved_idempotent(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1110)
    svc = ChatService(session)

    r1 = await svc.get_or_create_saved(u1)
    r2 = await svc.get_or_create_saved(u1)

    assert (
        r1["conversation"]["id"]
        == r2["conversation"]["id"]
    )


async def test_pin_chat_not_member(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1111)
    svc = ChatService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.pin_chat(u1, 9999)

    assert exc.value.status_code == 403


async def test_get_member_ids(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, 1112)
    u2 = await _make_user(session, 1113)
    svc = ChatService(session)
    result = await svc.create_dm(u1, u2)
    cid = result["conversation"]["id"]

    members = await svc.get_member_ids(cid)

    assert set(members) == {u1, u2}
