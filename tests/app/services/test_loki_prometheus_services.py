from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.loki_service import (
    LokiServiceError,
    build_query,
)
from app.services.prometheus_service import (
    PrometheusServiceError,
    metric_expr,
    query_range,
)


def test_loki_build_query_simple() -> None:
    q = build_query(
        selectors={"service": "dotsound-backend"}
    )
    assert (
        q == '{service="dotsound-backend"}'
    )


def test_loki_build_query_with_contains() -> None:
    q = build_query(
        selectors={"container": "backend"},
        contains="error",
    )
    assert q == '{container="backend"} |= "error"'


def test_loki_build_query_rejects_unknown_label() -> None:
    with pytest.raises(LokiServiceError):
        build_query(
            selectors={"sql_inject": "x"}
        )


def test_loki_build_query_rejects_disallowed_level() -> None:
    with pytest.raises(LokiServiceError):
        build_query(selectors={"level": "boom"})


def test_loki_build_query_rejects_dangerous_value() -> None:
    with pytest.raises(LokiServiceError):
        build_query(
            selectors={
                "container": 'a"} | foo |='
            }
        )


def test_loki_build_query_requires_selector() -> None:
    with pytest.raises(LokiServiceError):
        build_query(selectors={})


def test_loki_build_query_rejects_dangerous_contains() -> None:
    with pytest.raises(LokiServiceError):
        build_query(
            selectors={"service": "x"},
            contains='" | label_format foo="bar',
        )


def test_loki_build_query_safe_contains() -> None:
    q = build_query(
        selectors={"service": "x"},
        contains="hello world",
    )
    assert q == '{service="x"} |= "hello world"'


def test_prometheus_metric_expr_known() -> None:
    expr = metric_expr("rps_5m")
    assert "http_requests_total" in expr


def test_prometheus_metric_expr_unknown() -> None:
    with pytest.raises(PrometheusServiceError):
        metric_expr("system.os.exec(rm -rf /)")


@pytest.mark.anyio
async def test_prometheus_query_range_without_url_returns_empty_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.prometheus_service.settings",
        SimpleNamespace(prometheus_url=""),
    )
    out = await query_range(
        metric="rps_5m",
        start=0.0,
        end=120.0,
        step_seconds=30,
    )
    assert out["status"] == "success"
    assert out["data"]["resultType"] == "matrix"
    assert out["data"]["result"] == []
