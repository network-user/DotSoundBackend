import importlib
import sys
import types
from collections.abc import AsyncIterator, Iterator
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger, Boolean, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

import app.models  # noqa: F401
from app.dependencies import get_db
from app.main import create_app
from app.models.base import Base

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _from_buffer_for_tests(data: bytes, mime: bool = True) -> str:
    if data.startswith(b"ID3") or data[0:2] in (
        b"\xff\xfb",
        b"\xff\xf3",
        b"\xff\xf2",
    ):
        return "audio/mpeg"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b"ftyp" in data[:32]:
        return "video/mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3" or b"webm" in data[:200]:
        return "video/webm"
    return "application/octet-stream"


def _ensure_magic_test_stub() -> None:
    if "magic" in sys.modules:
        return
    try:
        mod = importlib.import_module("magic")
        mod.from_buffer(b"\xff\xfb" + b"\x00" * 16, mime=True)
    except Exception:
        m = types.ModuleType("magic")
        m.from_buffer = _from_buffer_for_tests
        sys.modules["magic"] = m


_ensure_magic_test_stub()


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(
    _type: BigInteger,
    _compiler: object,
    **_kwargs: object,
) -> str:
    return "INTEGER"


@event.listens_for(Base, "init", propagate=True)
def _set_boolean_defaults(
    target: object,
    _args: object,
    kwargs: dict[str, object],
) -> None:
    for attr in type(target).__mapper__.column_attrs:
        col = attr.columns[0]
        if (
            isinstance(col.type, Boolean)
            and attr.key not in kwargs
            and col.server_default is not None
        ):
            sd = col.server_default.arg
            if isinstance(sd, str):
                setattr(
                    target,
                    attr.key,
                    sd.lower() in ("true", "1"),
                )


@pytest.fixture(autouse=True)
def _disable_rate_limit() -> Iterator[None]:
    with patch(
        "app.core.rate_limit.limiter.enabled",
        False,
    ):
        yield


@pytest.fixture(autouse=True)
def _disable_sc_strict_import_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Default SC import behavior in tests: don't reject on verify fail.

    Tests rarely mock the actual SoundCloud HTTP layer, so the
    post-import verification call will return False (no network).
    With ``sc_strict_import_verify=True`` (the production default)
    that would turn every SC import test into a 422. Override to
    False here; specific tests that exercise the strict-verify branch
    flip it back to True with ``monkeypatch.setattr``.
    """
    from app.config import settings

    monkeypatch.setattr(
        settings,
        "sc_strict_import_verify",
        False,
        raising=False,
    )
    yield


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(
    db_engine: AsyncEngine,
) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        db_engine, expire_on_commit=False
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def client(
    db_engine: AsyncEngine,
) -> AsyncIterator[AsyncClient]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        db_engine, expire_on_commit=False
    )

    async def _override_get_db() -> AsyncSession:
        async with factory() as session:
            try:
                yield session  # type: ignore[misc]
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = _override_get_db

    with patch(
        "app.middlewares.admin_audit_log.AsyncSessionLocal",
        factory,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
        ) as ac:
            yield ac  # type: ignore[misc]


async def _fake_put_cas(
    data: bytes,
    content_sha256_hex: str,
    extension: str,
    content_type: str,
) -> str:
    from app.core.s3 import build_cas_audio_key

    return build_cas_audio_key(content_sha256_hex, extension)


@pytest.fixture
def mock_s3() -> Iterator[AsyncMock]:
    with (
        patch(
            "app.core.s3.put_cas_audio",
            new_callable=AsyncMock,
            side_effect=_fake_put_cas,
        ) as m,
        patch(
            "app.core.s3.upload_audio",
            new_callable=AsyncMock,
            return_value="anon/testkey.mp3",
        ),
    ):
        yield m


@pytest.fixture
def mock_taskiq() -> Iterator[None]:
    _lyrics_kiq = MagicMock()
    _lyrics_kiq.task_id = "test-lyrics-task"
    with (
        patch(
            "app.services.upload_service" ".transcode_and_upload.kiq",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.upload_service" ".generate_and_upload_cover.kiq",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.lyrics_worker.catalog_only_lyrics_task.kiq",
            new_callable=AsyncMock,
            return_value=_lyrics_kiq,
        ),
    ):
        yield


async def create_test_user(
    client: AsyncClient,
    telegram_id: int,
    **kwargs: object,
) -> dict[str, Any]:
    # POST /api/v1/users is internal-only (require_internal_caller).
    # The ASGI test client's 127.0.0.1 is inside the debug allowlist,
    # so this server-to-server style upsert is permitted in tests.
    payload = {
        "telegram_id": telegram_id,
        "first_name": kwargs.get("first_name", "Test"),
        "username": kwargs.get("username"),
        "last_name": kwargs.get("last_name"),
    }
    r = await client.post("/api/v1/users", json=payload)
    assert r.status_code == 200
    return r.json()


async def create_test_track(
    client: AsyncClient,
    title: str = "Test Track",
    uploader_id: int | None = None,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "title": title,
        "upload_terms_accepted": "true",
    }
    headers: dict[str, str] = {}
    if uploader_id is not None:
        headers = await auth_headers(client, uploader_id)

    _lyrics_kiq = MagicMock()
    _lyrics_kiq.task_id = "test-lyrics-task"
    with (
        patch(
            "app.core.s3.upload_object",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.file_validator.validate_audio",
            return_value=None,
        ),
        patch(
            "app.services.file_validator.scan_for_malware",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.track_ingest_schedule_service"
            ".schedule_new_track_background_jobs",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.upload_service" ".transcode_and_upload.kiq",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.upload_service" ".generate_and_upload_cover.kiq",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.lyrics_worker.catalog_only_lyrics_task.kiq",
            new_callable=AsyncMock,
            return_value=_lyrics_kiq,
        ),
    ):
        r = await client.post(
            "/api/v1/tracks/upload",
            data=data,
            headers=headers,
            files={
                "file": (
                    "t.mp3",
                    BytesIO(b"\xff\xfb" + b"\x00" * 64),
                    "audio/mpeg",
                )
            },
        )
    assert r.status_code == 201
    return r.json()


async def auth_headers(
    client: AsyncClient,
    user_id: int,
) -> dict[str, str]:
    response = await client.post(f"/api/v1/auth/mock/{user_id}")
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def admin_bearer_for_user(
    _client: AsyncClient,
    db_session: AsyncSession,
    *,
    user_id: int,
) -> dict[str, str]:
    from secrets import token_hex

    from dotsound_private_core.services.admin_security_policy import (
        ADMIN_SESSION_TTL_SECONDS,
    )
    from sqlalchemy import update

    from app.core.auth import create_admin_token
    from app.models.user import User
    from app.repositories.admin_device import (
        AdminDeviceRepository,
    )
    from app.repositories.admin_session import (
        AdminSessionRepository,
    )

    await db_session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            is_admin=True,
            admin_init=True,
        )
    )
    await db_session.commit()
    dev_repo = AdminDeviceRepository(db_session)
    dev = await dev_repo.create_pending(
        user_id=user_id,
        fingerprint_hash=token_hex(16),
        label="t",
        ip="127.0.0.1",
        ua="test",
    )
    await dev_repo.trust(dev)
    sess_repo = AdminSessionRepository(db_session)
    jti = token_hex(16)
    rjti = token_hex(16)
    await sess_repo.create(
        user_id=user_id,
        device_id=dev.id,
        jti=jti,
        refresh_jti=rjti,
        ip="127.0.0.1",
        ua="test",
        ttl_seconds=ADMIN_SESSION_TTL_SECONDS,
    )
    await db_session.commit()
    token = create_admin_token(
        user_id=user_id,
        jti=jti,
        device_id=dev.id,
        ttl_seconds=ADMIN_SESSION_TTL_SECONDS,
    )
    return {"Authorization": f"Bearer {token}"}


async def grant_admin_capability(
    db_session: AsyncSession,
    user_id: int,
    capability: str,
) -> None:
    from datetime import UTC, datetime

    from app.models.admin_capability import AdminCapability

    db_session.add(
        AdminCapability(
            user_id=user_id,
            capability=capability,
            granted_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
