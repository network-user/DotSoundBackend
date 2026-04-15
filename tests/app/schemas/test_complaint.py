from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintSubmitResponse,
)


def test_complaint_create_valid() -> None:
    req = ComplaintCreate(
        track_id=1,
        reason="This is copyrighted material",
    )
    assert req.track_id == 1
    assert req.reason == "This is copyrighted material"
    assert req.contact_email is None


def test_complaint_create_with_email() -> None:
    req = ComplaintCreate(
        track_id=1,
        reason="Copyrighted song here",
        contact_email="user@example.com",
    )
    assert req.contact_email == "user@example.com"


def test_complaint_create_copyright_notice() -> None:
    req = ComplaintCreate(
        track_id=1,
        reason="Трек размещен без разрешения правообладателя",
        reason_type="copyright",
        contact_email="rights@example.com",
        rightsholder_name="Rights Holder LLC",
        proof_url="https://example.com/proof",
    )
    assert req.reason_type == "copyright"
    assert req.rightsholder_name == "Rights Holder LLC"


def test_complaint_create_copyright_notice_requires_fields() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(
            track_id=1,
            reason="Трек размещен без разрешения правообладателя",
            reason_type="copyright",
        )


def test_complaint_create_reason_too_short() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(
            track_id=1,
            reason="Short",
        )


def test_complaint_create_reason_min_length() -> None:
    req = ComplaintCreate(
        track_id=1,
        reason="x" * 10,
    )
    assert len(req.reason) == 10


def test_complaint_create_reason_too_long() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(
            track_id=1,
            reason="x" * 1001,
        )


def test_complaint_create_reason_max_length() -> None:
    req = ComplaintCreate(
        track_id=1,
        reason="x" * 1000,
    )
    assert len(req.reason) == 1000


def test_complaint_create_invalid_email() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(
            track_id=1,
            reason="Copyrighted material!!!",
            contact_email="not-email",
        )


def test_complaint_create_missing_track_id() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(
            reason="Copyrighted material!!!"
        )


def test_complaint_create_missing_reason() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(track_id=1)


def test_complaint_response_valid() -> None:
    now = datetime(2024, 1, 1)
    resp = ComplaintResponse(
        id=1,
        track_id=2,
        reported_by_user_id=3,
        reason="Copyright",
        reason_type="other",
        contact_email=None,
        rightsholder_name=None,
        proof_url=None,
        is_resolved=False,
        created_at=now,
    )
    assert resp.id == 1
    assert resp.is_resolved is False


def test_complaint_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        ComplaintResponse(
            id=1,
            track_id=2,
            reported_by_user_id=3,
        )


def test_complaint_submit_response_valid() -> None:
    now = datetime(2024, 6, 15)
    complaint = ComplaintResponse(
        id=10,
        track_id=5,
        reported_by_user_id=1,
        reason="Spam track",
        reason_type="other",
        contact_email=None,
        rightsholder_name=None,
        proof_url=None,
        is_resolved=False,
        created_at=now,
    )
    resp = ComplaintSubmitResponse(
        complaint=complaint,
        track_hidden=True,
    )
    assert resp.track_hidden is True
    assert resp.complaint.id == 10
