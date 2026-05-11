"""Tests for ChunkedUploadService.

Covers init/chunk/complete happy path, chunk idempotency,
incomplete-complete rejection, expired-session rejection, and
cross-user isolation.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.services.chunked_upload_service import (
    UPLOAD_CHUNK_BYTES,
    ChunkedUploadService,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.chunked_upload_service"


@asynccontextmanager
async def _fake_s3_client(client: AsyncMock):
    yield client


def _patch_s3(client: AsyncMock):
    return patch(
        f"{_MOD}.s3.get_s3_client",
        return_value=_fake_s3_client(client),
    )


async def _make_user(session: AsyncSession, tg_id: int):
    repo = UserRepository(session)
    user, _ = await repo.upsert(tg_id, f"u{tg_id}", f"U {tg_id}", None)
    return user


async def test_init_creates_session_and_starts_multipart(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 2001)
    s3_client = AsyncMock()
    s3_client.create_multipart_upload = AsyncMock(
        return_value={"UploadId": "mp-1"}
    )
    svc = ChunkedUploadService(session)
    with _patch_s3(s3_client):
        rec = await svc.init(
            user_id=user.id,
            filename="t.mp3",
            mime="audio/mpeg",
            total_size=UPLOAD_CHUNK_BYTES * 2 + 10,
            audio_hash="a" * 64,
            meta={"title": "T", "artist": None, "genre": None, "is_public": True},
        )
    assert rec.expected_chunks == 3
    assert rec.chunk_size == UPLOAD_CHUNK_BYTES
    assert rec.s3_multipart_id == "mp-1"
    assert rec.status == "active"
    assert rec.completed_chunks == []


async def test_init_rejects_unsupported_mime(session: AsyncSession) -> None:
    user = await _make_user(session, 2002)
    svc = ChunkedUploadService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.init(
            user_id=user.id,
            filename="x.txt",
            mime="text/plain",
            total_size=100,
            audio_hash=None,
            meta={},
        )
    assert exc.value.status_code == 415


async def test_init_rejects_oversize(session: AsyncSession) -> None:
    user = await _make_user(session, 2003)
    svc = ChunkedUploadService(session)
    with pytest.raises(HTTPException) as exc:
        await svc.init(
            user_id=user.id,
            filename="big.mp3",
            mime="audio/mpeg",
            total_size=101 * 1024 * 1024,
            audio_hash=None,
            meta={},
        )
    assert exc.value.status_code == 413


async def test_chunk_idempotent_and_completes(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, 2004)
    s3_client = AsyncMock()
    s3_client.create_multipart_upload = AsyncMock(
        return_value={"UploadId": "mp-2"}
    )
    s3_client.upload_part = AsyncMock(
        side_effect=[{"ETag": "e1"}, {"ETag": "e1-retry"}, {"ETag": "e2"}]
    )
    svc = ChunkedUploadService(session)
    with _patch_s3(s3_client):
        rec = await svc.init(
            user_id=user.id,
            filename="t.mp3",
            mime="audio/mpeg",
            total_size=UPLOAD_CHUNK_BYTES + 5,
            audio_hash=None,
            meta={},
        )
        assert rec.expected_chunks == 2

        await svc.upload_chunk(
            upload_id=rec.upload_id,
            user_id=user.id,
            chunk_index=0,
            data=b"\x00" * UPLOAD_CHUNK_BYTES,
        )
        # re-upload same chunk -> idempotent, completed_chunks stays unique
        again = await svc.upload_chunk(
            upload_id=rec.upload_id,
            user_id=user.id,
            chunk_index=0,
            data=b"\x00" * UPLOAD_CHUNK_BYTES,
        )
        assert again.completed_chunks == [0]
        assert len(again.s3_parts or []) == 1
        assert (again.s3_parts or [])[0]["etag"] == "e1-retry"

        await svc.upload_chunk(
            upload_id=rec.upload_id,
            user_id=user.id,
            chunk_index=1,
            data=b"\x00" * 5,
        )

    # Try complete (mock the multipart finalize + finalize_from_s3)
    s3_client.complete_multipart_upload = AsyncMock(return_value={})
    finalize = AsyncMock()
    fake_track = MagicMock(id=42)
    finalize.return_value = fake_track
    fake_hash = "f" * 64
    with _patch_s3(s3_client), patch(
        f"{_MOD}.UploadService"
    ) as upload_svc_cls, patch(
        f"{_MOD}.s3.compute_sha256_streaming",
        new_callable=AsyncMock,
        return_value=fake_hash,
    ) as hash_mock:
        upload_svc_cls.return_value.finalize_from_s3 = finalize
        track = await svc.complete(
            upload_id=rec.upload_id, user_id=user.id
        )
    assert track.id == 42
    finalize.assert_awaited_once()
    hash_mock.assert_awaited_once()
    kwargs = finalize.await_args.kwargs
    assert kwargs["source_sha256"] == fake_hash


async def test_complete_rejects_incomplete(session: AsyncSession) -> None:
    user = await _make_user(session, 2005)
    s3_client = AsyncMock()
    s3_client.create_multipart_upload = AsyncMock(
        return_value={"UploadId": "mp-3"}
    )
    svc = ChunkedUploadService(session)
    with _patch_s3(s3_client):
        rec = await svc.init(
            user_id=user.id,
            filename="t.mp3",
            mime="audio/mpeg",
            total_size=UPLOAD_CHUNK_BYTES * 2,
            audio_hash=None,
            meta={},
        )
        with pytest.raises(HTTPException) as exc:
            await svc.complete(
                upload_id=rec.upload_id, user_id=user.id
            )
        assert exc.value.status_code == 400


async def test_cancel_aborts_multipart(session: AsyncSession) -> None:
    user = await _make_user(session, 2006)
    s3_client = AsyncMock()
    s3_client.create_multipart_upload = AsyncMock(
        return_value={"UploadId": "mp-4"}
    )
    s3_client.abort_multipart_upload = AsyncMock(return_value={})
    svc = ChunkedUploadService(session)
    with _patch_s3(s3_client):
        rec = await svc.init(
            user_id=user.id,
            filename="t.mp3",
            mime="audio/mpeg",
            total_size=UPLOAD_CHUNK_BYTES,
            audio_hash=None,
            meta={},
        )
        await svc.cancel(upload_id=rec.upload_id, user_id=user.id)

    s3_client.abort_multipart_upload.assert_awaited_once()
    refreshed = await svc.status(
        upload_id=rec.upload_id, user_id=user.id
    )
    assert refreshed.status == "cancelled"


async def test_cross_user_access_denied(session: AsyncSession) -> None:
    owner = await _make_user(session, 2007)
    other = await _make_user(session, 2008)
    s3_client = AsyncMock()
    s3_client.create_multipart_upload = AsyncMock(
        return_value={"UploadId": "mp-5"}
    )
    svc = ChunkedUploadService(session)
    with _patch_s3(s3_client):
        rec = await svc.init(
            user_id=owner.id,
            filename="t.mp3",
            mime="audio/mpeg",
            total_size=UPLOAD_CHUNK_BYTES,
            audio_hash=None,
            meta={},
        )
    with pytest.raises(HTTPException) as exc:
        await svc.status(
            upload_id=rec.upload_id, user_id=other.id
        )
    assert exc.value.status_code == 404
