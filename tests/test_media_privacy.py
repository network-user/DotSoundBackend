import io

import pytest
from PIL import Image
from PIL.ExifTags import Base as ExifBase

from app.services.media_service import (
    create_thumbnail,
    strip_metadata_and_compress,
)

pytestmark = pytest.mark.anyio


def _make_image_with_exif() -> bytes:
    img = Image.new("RGB", (2000, 1500), "red")
    from PIL.ExifTags import IFD

    exif = img.getexif()
    exif[0x010F] = "TestCamera"
    exif[0x0110] = "ModelX"
    exif[0x0132] = "2025:01:01 00:00:00"

    gps_ifd = {
        1: "N",
        2: ((55, 1), (45, 1), (0, 1)),
        3: "E",
        4: ((37, 1), (35, 1), (0, 1)),
    }
    exif[0x8825] = gps_ifd

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_exif_stripped_from_processed_image() -> None:
    raw = _make_image_with_exif()
    processed, w, h = strip_metadata_and_compress(
        raw, max_size=800
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
    processed, w, h = strip_metadata_and_compress(
        raw, max_size=400
    )
    assert max(w, h) <= 400


def test_thumbnail_creation() -> None:
    raw = _make_image_with_exif()
    processed, _, _ = strip_metadata_and_compress(
        raw, max_size=800
    )
    thumb = create_thumbnail(processed, size=100)

    img = Image.open(io.BytesIO(thumb))
    assert max(img.size) <= 100


def test_output_is_webp() -> None:
    raw = _make_image_with_exif()
    processed, _, _ = strip_metadata_and_compress(
        raw, max_size=800
    )
    img = Image.open(io.BytesIO(processed))
    assert img.format == "WEBP"


def test_original_exif_data_present() -> None:
    raw = _make_image_with_exif()
    img = Image.open(io.BytesIO(raw))
    exif = img.getexif()
    assert 0x010F in exif
    assert exif[0x010F] == "TestCamera"
