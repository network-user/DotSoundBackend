import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.schemas.user import UserCreate
from app.services.user_service import UserService

pytestmark = pytest.mark.anyio


async def test_register_or_update_creates_user(
    session: AsyncSession,
) -> None:
    svc = UserService(session)
    data = UserCreate(
        telegram_id=400,
        first_name="Alice",
        username="alice",
    )

    user, created = await svc.register_or_update(data)

    assert created is True
    assert user.telegram_id == 400
    assert user.first_name == "Alice"


async def test_register_or_update_updates_user(
    session: AsyncSession,
) -> None:
    svc = UserService(session)
    data = UserCreate(
        telegram_id=401,
        first_name="Bob",
        username="bob",
    )
    await svc.register_or_update(data)

    data2 = UserCreate(
        telegram_id=401,
        first_name="Bobby",
        username="bobby",
    )
    user, created = await svc.register_or_update(
        data2
    )

    assert created is False
    assert user.first_name == "Bobby"


async def test_register_or_update_no_telegram_id(
    session: AsyncSession,
) -> None:
    svc = UserService(session)
    data = UserCreate(
        telegram_id=None,
        first_name="NoId",
    )

    with pytest.raises(ValueError):
        await svc.register_or_update(data)


async def test_get_or_create_by_email(
    session: AsyncSession,
) -> None:
    svc = UserService(session)

    user, created = await svc.get_or_create_by_email(
        "test@example.com"
    )

    assert created is True
    assert user.email == "test@example.com"


async def test_get_or_create_by_email_existing(
    session: AsyncSession,
) -> None:
    svc = UserService(session)
    await svc.get_or_create_by_email(
        "dupe@example.com"
    )
    user, created = await svc.get_or_create_by_email(
        "dupe@example.com"
    )

    assert created is False


async def test_get_by_id(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        402, "u", "Test", None
    )

    svc = UserService(session)
    found = await svc.get_by_id(user.id)

    assert found is not None
    assert found.id == user.id


async def test_get_by_id_not_found(
    session: AsyncSession,
) -> None:
    svc = UserService(session)

    found = await svc.get_by_id(9999)

    assert found is None


async def test_get_by_telegram_id(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        403, "u", "Test", None
    )

    svc = UserService(session)
    found = await svc.get_by_telegram_id(403)

    assert found is not None
    assert found.telegram_id == 403


async def test_update_display_name(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        404, "u", "Test", None
    )

    svc = UserService(session)
    updated = await svc.update_display_name(
        user.id, "DJ Test"
    )

    assert updated is not None
    assert updated.display_name == "DJ Test"


async def test_update_display_name_not_found(
    session: AsyncSession,
) -> None:
    svc = UserService(session)

    updated = await svc.update_display_name(
        9999, "Ghost"
    )

    assert updated is None


async def test_update_avatar_key(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        405, "u", "Test", None
    )

    svc = UserService(session)
    updated = await svc.update_avatar_key(
        user.id, "avatar/new.png"
    )

    assert updated is not None
    assert updated.avatar_key == "avatar/new.png"
