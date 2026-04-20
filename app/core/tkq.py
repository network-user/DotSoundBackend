import taskiq_redis

from app.config import settings
from app.core import log_setup  # noqa: F401 — installs debug file logs on import

redis_broker = taskiq_redis.ListQueueBroker(
    url=settings.redis_url,
).with_result_backend(
    taskiq_redis.RedisAsyncResultBackend(
        redis_url=settings.redis_url,
    ),
)

broker = redis_broker
