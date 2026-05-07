from datetime import UTC, datetime, timedelta

from app.models.compute_worker import ComputeWorker
from app.services.worker_job_control import (
    package_version_below_min,
    worker_claims_blocked,
)


def test_package_version_below_min_strict() -> None:
    assert package_version_below_min(
        "0.1.0",
        "0.2.0",
    ) is True


def test_package_version_not_below() -> None:
    assert package_version_below_min(
        "0.3.1",
        "0.2.0",
    ) is False


def test_package_version_empty_floor() -> None:
    assert package_version_below_min(
        "0.0.1",
        "",
    ) is False


def test_worker_claims_blocked_active_until() -> None:
    w = ComputeWorker(
        id="w_worker_job_control_t1",
        name="t",
        profile="gpu_full",
        token_hash="x",
    )
    w.claims_paused_until = datetime.now(UTC) + timedelta(
        hours=1,
    )
    assert worker_claims_blocked(w) is True


def test_worker_claims_blocked_no_until() -> None:
    w = ComputeWorker(
        id="w_worker_job_control_t2",
        name="t",
        profile="gpu_full",
        token_hash="x",
    )
    w.claims_paused_until = None
    assert worker_claims_blocked(w) is False
