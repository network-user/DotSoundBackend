import pytest
from pydantic import ValidationError

from app.schemas.eq import (
    EqSettingsRequest,
    EqSettingsResponse,
)

VALID_BANDS = [0.0, 1.0, -1.0, 2.5, -3.0, 0.0, 6.0, -12.0]


def test_eq_request_valid() -> None:
    req = EqSettingsRequest(bands=VALID_BANDS)
    assert req.bands == VALID_BANDS
    assert req.preset is None


def test_eq_request_with_preset() -> None:
    req = EqSettingsRequest(
        preset="rock", bands=VALID_BANDS
    )
    assert req.preset == "rock"


def test_eq_request_too_few_bands() -> None:
    with pytest.raises(ValidationError) as exc_info:
        EqSettingsRequest(bands=[0.0] * 7)
    assert "bands must have 8 values" in str(
        exc_info.value
    )


def test_eq_request_too_many_bands() -> None:
    with pytest.raises(ValidationError) as exc_info:
        EqSettingsRequest(bands=[0.0] * 9)
    assert "bands must have 8 values" in str(
        exc_info.value
    )


def test_eq_request_empty_bands() -> None:
    with pytest.raises(ValidationError):
        EqSettingsRequest(bands=[])


def test_eq_request_band_too_high() -> None:
    bands = [0.0] * 7 + [12.1]
    with pytest.raises(ValidationError) as exc_info:
        EqSettingsRequest(bands=bands)
    assert "between -12 and 12" in str(
        exc_info.value
    )


def test_eq_request_band_too_low() -> None:
    bands = [-12.1] + [0.0] * 7
    with pytest.raises(ValidationError) as exc_info:
        EqSettingsRequest(bands=bands)
    assert "between -12 and 12" in str(
        exc_info.value
    )


def test_eq_request_boundary_values() -> None:
    bands = [12.0, -12.0, 12.0, -12.0, 12.0, -12.0, 12.0, -12.0]
    req = EqSettingsRequest(bands=bands)
    assert req.bands == bands


def test_eq_request_all_zeros() -> None:
    bands = [0.0] * 8
    req = EqSettingsRequest(bands=bands)
    assert req.bands == bands


def test_eq_request_preset_too_long() -> None:
    with pytest.raises(ValidationError):
        EqSettingsRequest(
            preset="x" * 51, bands=VALID_BANDS
        )


def test_eq_request_preset_max_length() -> None:
    req = EqSettingsRequest(
        preset="x" * 50, bands=VALID_BANDS
    )
    assert len(req.preset) == 50


def test_eq_request_missing_bands() -> None:
    with pytest.raises(ValidationError):
        EqSettingsRequest()


def test_eq_request_wrong_type_bands() -> None:
    with pytest.raises(ValidationError):
        EqSettingsRequest(bands="not a list")


def test_eq_response_valid() -> None:
    resp = EqSettingsResponse(
        preset="flat", bands=VALID_BANDS
    )
    assert resp.preset == "flat"
    assert resp.bands == VALID_BANDS


def test_eq_response_no_preset() -> None:
    resp = EqSettingsResponse(
        preset=None, bands=[0.0] * 8
    )
    assert resp.preset is None
