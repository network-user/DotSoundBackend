import taskiq_redis
from taskiq import AsyncBroker, AsyncResultBackend
from app.config import settings

# Инициализация брокера Redis
# В Docker-compose адрес будет redis://redis:6379/0
redis_broker = taskiq_redis.ListQueueBroker(
    url=settings.redis_url,
).with_result_backend(
    taskiq_redis.RedisAsyncResultBackend(
        url=settings.redis_url,
    ),
)

# Экспортируем брокер для использования в воркере и приложении
broker = redis_broker
