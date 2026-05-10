"""Prometheus HTTP client for the admin dashboard.

The endpoint accepts only a fixed list of metric expressions
(``ALLOWED_METRICS``); arbitrary PromQL is rejected so a logged-in
admin cannot turn the panel into an open-ended query interface.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

ALLOWED_METRICS: dict[str, str] = {
    "rps_5m": "sum(rate(http_requests_total[5m]))",
    "error_rate_5m": "sum(rate(http_errors_total[5m]))",
    "latency_p95_5m": (
        "histogram_quantile(0.95, "
        "sum by (le) ("
        "rate(http_request_duration_seconds_bucket[5m])"
        "))"
    ),
    "latency_p50_5m": (
        "histogram_quantile(0.50, "
        "sum by (le) ("
        "rate(http_request_duration_seconds_bucket[5m])"
        "))"
    ),
    "active_websockets": ("sum(active_websocket_connections)"),
    "radio_requests_5m": ("sum(rate(radio_requests_total[5m]))"),
    "radio_guard_hits_5m": ("sum(rate(radio_guard_hits_total[5m]))"),
    "radio_queue_size_avg_5m": (
        "avg(rate(radio_queue_size_sum[5m]) / "
        "clamp_min(rate(radio_queue_size_count[5m]), 1e-9))"
    ),
    "container_cpu_5m": (
        "sum by (name) (" "rate(container_cpu_usage_seconds_total[5m])" ")"
    ),
    "container_mem": (
        "sum by (name) (" "container_memory_working_set_bytes" ")"
    ),
    "recsys_completion_rate_5m": (
        "sum by (surface) ("
        "rate(recsys_listen_outcomes_total"
        '{outcome="completed"}[5m])'
        ") / clamp_min(sum by (surface) ("
        "rate(recsys_listen_outcomes_total[5m])"
        "), 1e-9)"
    ),
    "recsys_skip_quick_rate_5m": (
        "sum by (surface) ("
        "rate(recsys_listen_outcomes_total"
        '{outcome="skipped_quick"}[5m])'
        ") / clamp_min(sum by (surface) ("
        "rate(recsys_listen_outcomes_total[5m])"
        "), 1e-9)"
    ),
    "recsys_save_rate_5m": (
        "sum by (surface) ("
        "rate(recsys_save_actions_total"
        '{action="playlist_add"}[5m])'
        ") / clamp_min(sum by (surface) ("
        "rate(recsys_listen_outcomes_total[5m])"
        "), 1e-9)"
    ),
    "recsys_pipeline_p95_5m": (
        "histogram_quantile(0.95, "
        "sum by (le, surface, stage) ("
        "rate(recsys_pipeline_seconds_bucket[5m])"
        "))"
    ),
    "recsys_listen_position_p50_5m": (
        "histogram_quantile(0.50, "
        "sum by (le, surface) ("
        "rate(recsys_listen_position_bucket[5m])"
        "))"
    ),
}


class PrometheusServiceError(Exception):
    pass


def _ensure_url() -> str:
    if not settings.prometheus_url:
        raise PrometheusServiceError("Prometheus is not configured")
    return settings.prometheus_url.rstrip("/")


def metric_expr(name: str) -> str:
    if name not in ALLOWED_METRICS:
        raise PrometheusServiceError(f"metric {name!r} is not allowed")
    return ALLOWED_METRICS[name]


async def query_instant(*, metric: str) -> dict[str, Any]:
    url = _ensure_url() + "/api/v1/query"
    params = {"query": metric_expr(metric)}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise PrometheusServiceError(
                f"Prometheus query failed: " f"HTTP {resp.status_code}"
            )
        return dict(resp.json())


async def query_range(
    *,
    metric: str,
    start: float,
    end: float,
    step_seconds: int = 30,
) -> dict[str, Any]:
    if step_seconds <= 0 or step_seconds > 3600:
        raise PrometheusServiceError("step_seconds out of bounds")
    if end <= start:
        raise PrometheusServiceError("end must be after start")
    if (end - start) > 7 * 24 * 3600:
        raise PrometheusServiceError("range too wide (max 7 days)")
    url = _ensure_url() + "/api/v1/query_range"
    params = {
        "query": metric_expr(metric),
        "start": str(start),
        "end": str(end),
        "step": str(step_seconds),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise PrometheusServiceError(
                f"Prometheus range query failed: " f"HTTP {resp.status_code}"
            )
        return dict(resp.json())


__all__ = [
    "ALLOWED_METRICS",
    "PrometheusServiceError",
    "metric_expr",
    "query_instant",
    "query_range",
]
