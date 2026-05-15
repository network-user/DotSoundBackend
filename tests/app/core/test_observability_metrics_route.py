from app.core.observability import _metrics_route_present
from app.main import create_app


def test_each_create_app_instance_has_metrics_route() -> None:
    first = create_app()
    second = create_app()
    assert _metrics_route_present(first)
    assert _metrics_route_present(second)
