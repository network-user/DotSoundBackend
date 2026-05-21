import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.services import cover_regen_worker
from app.services.cover_regen_worker import (
    _build_new_keys,
    _process_one,
    _split_cover_key,
    _thumb_key_for,
)
from app.services.media_service import strip_metadata_and_compress

pytestmark = pytest.mark.anyio


def test_split_cover_key_uuid_branch() -> None:
    out = _split_cover_key("covers/1/abc123.webp")
    assert out == ("1", "abc123.webp")


def test_split_cover_key_anon() -> None:
    out = _split_cover_key("covers/anon/deadbeef.webp")
    assert out == ("anon", "deadbeef.webp")


def test_split_cover_key_rejects_non_covers_prefix() -> None:
    assert _split_cover_key("image-blobs/aa/abc.webp") is None
    assert _split_cover_key("avatars/1/abc.webp") is None
    assert _split_cover_key("") is None


def test_split_cover_key_rejects_short_path() -> None:
    assert _split_cover_key("covers/justone") is None
    assert _split_cover_key("covers/") is None


def test_thumb_key_for_replaces_suffix() -> None:
    out = _thumb_key_for("covers/1/abc.webp")
    assert out == "covers/1/abc_thumb.webp"


def test_thumb_key_for_rejects_non_webp() -> None:
    assert _thumb_key_for("covers/1/abc.jpg") is None
    assert _thumb_key_for("") is None


def test_build_new_keys_uses_owner_and_uuid_pair() -> None:
    img, thumb = _build_new_keys("anon")
    assert img.startswith("covers/anon/")
    assert img.endswith(".webp")
    assert thumb.startswith("covers/anon/")
    assert thumb.endswith("_thumb.webp")
    base_img = img[len("covers/anon/") : -len(".webp")]
    base_thumb = thumb[len("covers/anon/") : -len("_thumb.webp")]
    assert base_img == base_thumb


def _make_jpeg(w: int = 2000, h: int = 1500) -> bytes:
    img = Image.new("RGB", (w, h), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_new_defaults_compress_more_than_old() -> None:
    raw = _make_jpeg()
    old_bytes, _, _ = strip_metadata_and_compress(
        raw, max_size=800, quality=80
    )
    new_bytes, w, h = strip_metadata_and_compress(
        raw, max_size=640, quality=70
    )
    assert len(new_bytes) < len(old_bytes)
    assert max(w, h) <= 640


async def test_process_one_skips_image_blobs_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download = AsyncMock()
    upload = AsyncMock()
    monkeypatch.setattr(
        "app.services.cover_regen_worker.s3.download_object",
        download,
    )
    monkeypatch.setattr(
        "app.services.cover_regen_worker.s3.upload_object",
        upload,
    )

    ok, saved = await _process_one(
        track_id=42,
        cover_key="image-blobs/aa/deadbeef.webp",
        updated_at=None,
        now=datetime.now(UTC),
    )

    assert ok is False
    assert saved == 0
    download.assert_not_awaited()
    upload.assert_not_awaited()


async def test_process_one_skips_avatars_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download = AsyncMock()
    monkeypatch.setattr(
        "app.services.cover_regen_worker.s3.download_object",
        download,
    )

    ok, saved = await _process_one(
        track_id=7,
        cover_key="avatars/1/abc.webp",
        updated_at=None,
        now=datetime.now(UTC),
    )

    assert ok is False
    assert saved == 0
    download.assert_not_awaited()


async def test_process_one_skips_when_adapter_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download = AsyncMock()
    monkeypatch.setattr(
        "app.services.cover_regen_worker.s3.download_object",
        download,
    )
    monkeypatch.setattr(
        cover_regen_worker.cover_regen_adapter,
        "should_regen_cover",
        lambda **_: False,
    )

    ok, saved = await _process_one(
        track_id=99,
        cover_key="covers/1/abc.webp",
        updated_at=None,
        now=datetime.now(UTC),
    )

    assert ok is False
    assert saved == 0
    download.assert_not_awaited()
