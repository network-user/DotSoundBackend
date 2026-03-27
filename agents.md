# DotSoundBackend — Agent Context

## Проект
DotSound — музыкальная платформа в Telegram (SoundCloud-style, UGC, без рекламы).
Этот репозиторий: FastAPI-бэкенд, PostgreSQL, MinIO. Вся бизнес-логика здесь.
Связанный репозиторий: `DotSoundBot` (бот + Mini App, только визуал).

## Стек
- Python 3.12
- FastAPI (async, OpenAPI из коробки)
- SQLAlchemy 2.x async + asyncpg (PostgreSQL driver)
- Alembic (миграции)
- aioboto3 (MinIO S3 async)
- pydantic-settings (конфиг из env)
- Инфраструктура: Docker (PostgreSQL 16 + MinIO)

## Соглашения кода
- Линтер: **Ruff** | Форматтер: **Black** | Type checker: **Mypy strict**
- Длина строки: **79 символов**
- **Без комментариев** — код самодокументируется через имена
- Докстринги только там, где сигнатура не передаёт смысл
- **Полная асинхронность**: async/await везде без исключений
- Настройки только через `app/config.py` (pydantic-settings). `os.environ` напрямую — запрещено
- **После каждой новой фичи обязательно пишем тесты** (pytest + anyio)

## Архитектурные слои
```
api/v1/  →  services/  →  repositories/  →  models/
```
- `api/v1/` — HTTP граница: парсинг запроса, вызов сервиса, возврат схемы. Без доступа к БД напрямую.
- `services/` — бизнес-логика. Вызывает репозитории. Получает `AsyncSession` через DI.
- `repositories/` — только запросы к БД. Возвращает ORM-модели или скаляры.
- `models/` — только определения таблиц SQLAlchemy.
- `schemas/` — Pydantic модели запросов/ответов. Никогда не импортировать ORM-модели сюда.

## Правила DI
- Сессии БД только через `dependencies.get_db()`. Никогда не инстанциировать сессии вручную.
- S3-клиент только через `app/core/s3.py` (`get_s3_client()`). Никогда не создавать boto3-клиенты инлайн.
- `app = create_app()` — фабрика. Тесты создают свой экземпляр приложения.

## Структура репозитория
```
DotSoundBackend/
├── app/
│   ├── main.py              # create_app() -> FastAPI, lifespan
│   ├── config.py            # AppSettings(BaseSettings)
│   ├── dependencies.py      # get_db, get_settings
│   ├── api/
│   │   ├── router.py        # api_router prefix="/api/v1"
│   │   └── v1/
│   │       └── health.py    # GET /api/v1/health
│   ├── core/
│   │   ├── db.py            # async_engine, AsyncSessionLocal
│   │   ├── s3.py            # get_s3_client() context manager
│   │   └── logging.py       # configure_logging()
│   ├── models/
│   │   └── base.py          # Base, TimestampMixin
│   ├── schemas/
│   │   └── common.py        # HealthResponse, ErrorResponse
│   ├── services/            # бизнес-логика (Этап 2+)
│   ├── repositories/        # запросы к БД (Этап 2+)
│   └── static/mini_app/     # Mini App (HTML/CSS/JS)
├── alembic/                 # миграции
├── tests/
│   ├── conftest.py          # fixtures
│   └── test_health.py
├── docker-compose.yml       # PostgreSQL 16 + MinIO
├── alembic.ini
└── pyproject.toml
```

## Запуск локально
```bash
cp .env.example .env
docker compose up -d
poetry install
poetry run alembic upgrade head
poetry run python main.py    # uvicorn на :8000
```

## Тесты
```bash
poetry run pytest
```

## Lint / Format / Typecheck
```bash
poetry run ruff check .
poetry run black .
poetry run mypy app/
```

## Mini App
Статические файлы: `app/static/mini_app/`.
Доступны по адресу: `/mini_app/`.
Вызывает бэкенд через относительные URL (`/api/v1/...`).
Для работы в Telegram требуется HTTPS (настраивается на уровне деплоя).
