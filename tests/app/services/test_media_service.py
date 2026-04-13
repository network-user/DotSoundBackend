import io

import pytest
from PIL import Image

from app.services.media_service import (
    create_thumbnail,
    process_image,
    strip_metadata_and_compress,
)

pytestmark = pytest.mark.anyio


def _make_image(
    w: int = 2000,
    h: int = 1500,
    mode: str = "RGB",
) -> bytes:
    img = Image.new(mode, (w, h), "red")
    buf = io.BytesIO()
    fmt = "PNG" if mode in ("RGBA", "LA", "P") else "JPEG"
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_image_with_exif() -> bytes:
    img = Image.new("RGB", (2000, 1500), "red")

    exif = img.getexif()
    exif[0x010F] = "TestCamera"
    exif[0x0110] = "ModelX"
    exif[0x0132] = "2025:01:01 00:00:00"

    gps_ifd = {
        1: "N",
        2: 55.75,
        3: "E",
        4: 37.58,
    }
    exif[0x8825] = gps_ifd

    buf = io.BytesIO()
    img.save(
        buf,
        format="JPEG",
        exif=exif.tobytes(),
    )
    return buf.getvalue()


def test_exif_stripped_from_processed_image() -> (
    None
):
    raw = _make_image_with_exif()
    processed, w, h = (
        strip_metadata_and_compress(
            raw, max_size=800
        )
    )

    result = Image.open(io.BytesIO(processed))
    exif = result.getexif()
    assert 0x010F not in exif
    assert 0x0110 not in exif
    assert 0x8825 not in exif
    assert w <= 800
    assert h <= 800


def test_image_resized_correctly() -> None:
    raw = _make_image_with_exif()
    processed, w, h = (
        strip_metadata_and_compress(
            raw, max_size=400
        )
    )
    assert max(w, h) <= 400


def test_thumbnail_creation() -> None:
    raw = _make_image_with_exif()
    processed, _, _ = (
        strip_metadata_and_compress(
            raw, max_size=800
        )
    )
    thumb = create_thumbnail(
        processed, size=100
    )

    img = Image.open(io.BytesIO(thumb))
    assert max(img.size) <= 100


def test_output_is_webp() -> None:
    raw = _make_image_with_exif()
    processed, _, _ = (
        strip_metadata_and_compress(
            raw, max_size=800
        )
    )
    img = Image.open(io.BytesIO(processed))
    assert img.format == "WEBP"


def test_original_exif_data_present() -> None:
    raw = _make_image_with_exif()
    img = Image.open(io.BytesIO(raw))
    exif = img.getexif()
    assert 0x010F in exif
    assert exif[0x010F] == "TestCamera"


def test_rgba_image_conversion() -> None:
    raw = _make_image(mode="RGBA")
    processed, w, h = (
        strip_metadata_and_compress(
            raw, max_size=800
        )
    )
    assert len(processed) > 0
    assert w <= 800


def test_palette_image_conversion() -> None:
    raw = _make_image(mode="P")
    processed, w, h = (
        strip_metadata_and_compress(
            raw, max_size=500
        )
    )
    assert len(processed) > 0


def test_small_image_not_resized() -> None:
    raw = _make_image(w=100, h=100)
    processed, w, h = (
        strip_metadata_and_compress(
            raw, max_size=800
        )
    )
    assert w == 100
    assert h == 100


def test_thumbnail_rgba() -> None:
    raw = _make_image(mode="RGBA")
    processed, _, _ = (
        strip_metadata_and_compress(
            raw, max_size=800
        )
    )
    thumb = create_thumbnail(
        processed, size=50
    )
    img = Image.open(io.BytesIO(thumb))
    assert max(img.size) <= 50


def test_process_image_returns_all() -> None:
    raw = _make_image(w=500, h=500)
    processed, thumb, w, h = process_image(
        raw, max_size=300
    )
    assert len(processed) > 0
    assert len(thumb) > 0
    assert max(w, h) <= 300


def test_process_image_default_size() -> None:
    raw = _make_image(w=100, h=100)
    processed, thumb, w, h = process_image(raw)
    assert len(processed) > 0
    assert len(thumb) > 0
