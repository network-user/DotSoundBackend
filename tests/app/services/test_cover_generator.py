import pytest

from app.services.cover_generator import (
    generate_cover,
)

pytestmark = pytest.mark.anyio


def test_generate_cover_returns_bytes() -> None:
    data = generate_cover("test_seed")

    assert isinstance(data, bytes)
    assert len(data) > 0


def test_generate_cover_png_header() -> None:
    data = generate_cover("seed_png")

    assert data[:4] == b"\x89PNG"


def test_generate_cover_deterministic() -> None:
    a = generate_cover("same_seed")
    b = generate_cover("same_seed")

    assert a == b


def test_generate_cover_different_seeds() -> None:
    a = generate_cover("seed_a")
    b = generate_cover("seed_b")

    assert a != b
