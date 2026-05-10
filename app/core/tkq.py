import structlog
import taskiq_redis
from taskiq import TaskiqEvents, TaskiqState

from app.config import settings
from app.core import (
    log_setup,  # noqa: F401 — installs debug file logs on import
)
from app.core.logging import apply_third_party_log_levels

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

redis_broker = taskiq_redis.ListQueueBroker(
    url=settings.redis_url,
).with_result_backend(
    taskiq_redis.RedisAsyncResultBackend(
        redis_url=settings.redis_url,
    ),
)

broker = redis_broker

# Lifecycle middleware: ties Taskiq executions kicked through
# ``app.services.background_jobs.enqueue`` to a BackgroundJob row,
# implements retries with exponential backoff and dead-letters
# terminal failures with an admin alert. Tasks kicked the legacy
# way (without bgjob_id label) are passed through untouched.
from app.core.taskiq_middleware import (  # noqa: E402
    BackgroundJobLifecycleMiddleware,
)

broker.add_middlewares(BackgroundJobLifecycleMiddleware())

# Before any other worker module runs (ES warmup, import side-effects),
# cap urllib3 / elastic_transport / httpx, etc. ``WORKER_STARTUP`` is too
# late — handlers may already have logged.
apply_third_party_log_levels(settings.log_third_party_level)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _worker_third_party_log_level(_st: TaskiqState) -> None:
    apply_third_party_log_levels(settings.log_third_party_level)


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _taskiq_worker_shutdown(_st: TaskiqState) -> None:
    from app.search.es_client import close_es
    from app.services import (
        import_queue_dispatcher,
        lyrics_global_orchestrator,
    )

    try:
        await import_queue_dispatcher.stop_dispatcher_task()
    except Exception:  # noqa: BLE001
        logger.exception("import_dispatcher_shutdown_failed")
    try:
        await lyrics_global_orchestrator.stop_orchestrator_task()
    except Exception:  # noqa: BLE001
        logger.exception("lyrics_orchestrator_shutdown_failed")
    try:
        await close_es()
    except Exception:  # noqa: BLE001
        logger.exception("elasticsearch_worker_close_failed")
    try:
        from app.services.soundcloud_service import close_sc_http_clients

        await close_sc_http_clients()
    except Exception:  # noqa: BLE001
        logger.exception("sc_http_client_close_failed")
