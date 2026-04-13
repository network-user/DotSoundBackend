import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository

pytestmark = pytest.mark.anyio


async def test_upsert_new_user(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)

    user, created = await repo.upsert(
        telegram_id=100,
        username="alice",
        first_name="Alice",
        last_name="W",
    )

    assert created is True
    assert user.telegram_id == 100
    assert user.username == "alice"
    assert user.avatar_seed is not None


async def test_upsert_existing_user(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    await repo.upsert(
        telegram_id=200,
        username="bob",
        first_name="Bob",
        last_name=None,
    )

    user, created = await repo.upsert(
        telegram_id=200,
        username="bobby",
        first_name="Robert",
        last_name="Z",
    )

    assert created is False
    assert user.username == "bobby"
    assert user.first_name == "Robert"


async def test_get_by_telegram_id(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    await repo.upsert(
        telegram_id=300,
        username="carol",
        first_name="Carol",
        last_name=None,
    )

    found = await repo.get_by_telegram_id(300)
    assert found is not None
    assert found.first_name == "Carol"

    missing = await repo.get_by_telegram_id(999)
    assert missing is None


async def test_get_by_email(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    await repo.upsert_by_email("Dan@Example.COM")

    found = await repo.get_by_email(
        "dan@example.com"
    )
    assert found is not None
    assert found.email == "dan@example.com"

    missing = await repo.get_by_email("nope@x.com")
    assert missing is None


async def test_search(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    await repo.upsert(
        telegram_id=400,
        username="searchme",
        first_name="Findable",
        last_name=None,
    )
    await repo.upsert(
        telegram_id=401,
        username="other",
        first_name="Other",
        last_name=None,
    )

    results = await repo.search("searchme")
    assert len(results) == 1
    assert results[0].username == "searchme"


async def test_update_display_name(
    session: AsyncSession,
) -> None:
    repo = UserRepository(session)
    user, _ = await repo.upsert(
        telegram_id=500,
        username="eve",
        first_name="Eve",
        last_name=None,
    )

    updated = await repo.update_display_name(
        user.id, "Eve Star"
    )
    assert updated is not None
    assert updated.display_name == "Eve Star"

    missing = await repo.update_display_name(
        9999, "Nope"
    )
    assert missing is None
