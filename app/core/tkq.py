import taskiq_redis
from taskiq import TaskiqEvents, TaskiqState

from app.config import settings
from app.core import (
    log_setup,  # noqa: F401 — installs debug file logs on import
)
from app.core.logging import apply_third_party_log_levels

redis_broker = taskiq_redis.ListQueueBroker(
    url=settings.redis_url,
).with_result_backend(
    taskiq_redis.RedisAsyncResultBackend(
        redis_url=settings.redis_url,
    ),
)

broker = redis_broker

# Before any other worker module runs (ES warmup, import side-effects),
# cap urllib3 / elastic_transport / httpx, etc. ``WORKER_STARTUP`` is too
# late — handlers may already have logged.
apply_third_party_log_levels(settings.log_third_party_level)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _worker_third_party_log_level(_st: TaskiqState) -> None:
    apply_third_party_log_levels(settings.log_third_party_level)
