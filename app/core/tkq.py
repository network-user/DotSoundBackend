import taskiq_redis

from app.config import settings

redis_broker = taskiq_redis.ListQueueBroker(
    url=settings.redis_url,
).with_result_backend(
    taskiq_redis.RedisAsyncResultBackend(
        redis_url=settings.redis_url,
    ),
)

broker = redis_broker
