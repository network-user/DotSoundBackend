import pytest
from pydantic import ValidationError

from app.schemas.common import (
    ErrorResponse,
    HealthResponse,
)


def test_health_response_valid() -> None:
    resp = HealthResponse(status="ok")
    assert resp.status == "ok"


def test_health_response_missing() -> None:
    with pytest.raises(ValidationError):
        HealthResponse()


def test_health_response_empty_string() -> None:
    resp = HealthResponse(status="")
    assert resp.status == ""


def test_error_response_valid() -> None:
    resp = ErrorResponse(detail="Not found")
    assert resp.detail == "Not found"


def test_error_response_missing() -> None:
    with pytest.raises(ValidationError):
        ErrorResponse()


def test_error_response_long_detail() -> None:
    resp = ErrorResponse(detail="x" * 5000)
    assert len(resp.detail) == 5000
