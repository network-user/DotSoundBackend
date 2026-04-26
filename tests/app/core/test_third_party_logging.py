from __future__ import annotations

import logging

import pytest

from app.core.logging import (
    _parse_log_level_name,
    apply_third_party_log_levels,
)


@pytest.fixture(autouse=True)
def _reset_third_party_loggers() -> object:
    yield
    apply_third_party_log_levels("WARNING")


def test_parse_log_level_falls_back_on_garbage() -> None:
    assert _parse_log_level_name("notalevelname") == logging.WARNING


def test_apply_sets_elastic_to_error() -> None:
    apply_third_party_log_levels("ERROR")
    assert (
        logging.getLogger("elastic_transport").level
        == logging.ERROR
    )


def test_apply_sets_debug() -> None:
    apply_third_party_log_levels("DEBUG")
    assert logging.getLogger("httpx").level == logging.DEBUG
