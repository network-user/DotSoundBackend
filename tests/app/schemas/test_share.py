import pytest
from pydantic import ValidationError

from app.schemas.share import ShareResponse


def test_share_response_valid() -> None:
    resp = ShareResponse(
        track_id=1,
        url="https://dotsound.app/t/1",
        telegram_share_url=(
            "https://t.me/share/url?url=x"
        ),
    )
    assert resp.track_id == 1
    assert "dotsound" in resp.url
    assert "t.me" in resp.telegram_share_url


def test_share_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        ShareResponse(track_id=1)


def test_share_response_missing_all() -> None:
    with pytest.raises(ValidationError):
        ShareResponse()


def test_share_response_wrong_type() -> None:
    with pytest.raises(ValidationError):
        ShareResponse(
            track_id="abc",
            url="http://x",
            telegram_share_url="http://y",
        )
