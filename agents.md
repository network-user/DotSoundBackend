# DotSoundBackend — Agent Context

## Проект
DotSound — музыкальная платформа в Telegram (SoundCloud-style, UGC, без рекламы).
Этот репозиторий: FastAPI-бэкенд, PostgreSQL, MinIO, Redis, Taskiq.
Связанный репозиторий: `DotSoundBot` (Telegram-бот, aiogram 3).

## Стек
- Python 3.12
- FastAPI (async, OpenAPI)
- SQLAlchemy 2.x async + asyncpg
- Alembic (миграции)
- aioboto3 (MinIO S3 async)
- Taskiq + Redis (фоновые задачи, транскодирование)
- pydantic-settings (конфиг из .env)
- structlog (логирование)
- slowapi (rate limiting через Redis)
- Инфраструктура: Docker Compose (PostgreSQL 16, MinIO, Redis 7)

## Соглашения кода
- Линтер: **Ruff** | Форматтер: **Black** | Type checker: **Mypy strict**
- Длина строки: **79 символов**
- **Без комментариев** — код самодокументируется через имена
- Докстринги только там, где сигнатура не передаёт смысл
- **Полная асинхронность**: async/await везде
- Настройки только через `app/config.py` (pydantic-settings)
- `os.environ` напрямую — запрещено

## Архитектурные слои
```
api/v1/ → services/ → repositories/ → models/
```
- `api/v1/` — HTTP граница: парсинг запроса, вызов сервиса, возврат схемы
- `services/` — бизнес-логика. Вызывает репозитории
- `repositories/` — только запросы к БД. Возвращает ORM-модели
- `models/` — определения таблиц SQLAlchemy
- `schemas/` — Pydantic модели запросов/ответов

## Правила DI
- Сессии БД только через `dependencies.get_db()`
- S3-клиент только через `app/core/s3.py` (`get_s3_client()`)
- `app = create_app()` — фабрика. Тесты создают свой экземпляр

## Безопасность
- `DEBUG=true` в .env включает dev-режим (mock auth, мягкие проверки)
- `DEBUG=false` — продакшн: JWT_SECRET обязан быть сменён, mock-эндпоинты отключены
- CORS настраивается через `ALLOWED_ORIGINS` в .env
- Rate limiting через Redis (работает при нескольких воркерах)

## Структура репозитория
```
DotSoundBackend/
├── app/
│   ├── main.py              # create_app() -> FastAPI, lifespan
│   ├── config.py            # AppSettings(BaseSettings)
│   ├── dependencies.py      # get_db, get_settings, get_current_user
│   ├── api/
│   │   ├── router.py        # api_router prefix="/api/v1"
│   │   └── v1/
│   │       ├── health.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── likes.py
│   │       ├── dislikes.py
│   │       ├── playlists.py
│   │       ├── soundcloud.py
│   │       ├── complaints.py
│   │       ├── metadata.py
│   │       ├── lyrics.py
│   │       ├── follows.py
│   │       ├── albums.py
│   │       ├── admin/
│   │       │   ├── tracks.py
│   │       │   ├── users.py
│   │       │   └── complaints.py
│   │       └── tracks/
│   │           ├── discovery.py
│   │           ├── user.py
│   │           ├── hls.py
│   │           └── playback.py
│   ├── core/
│   │   ├── db.py            # async_engine, AsyncSessionLocal
│   │   ├── s3.py            # S3 operations + ensure_bucket_exists
│   │   ├── auth.py          # JWT + Telegram HMAC
│   │   ├── logging.py       # structlog configuration
│   │   ├── rate_limit.py    # slowapi + Redis
│   │   └── tkq.py           # Taskiq Redis broker
│   ├── middlewares/
│   │   └── request_logging.py
│   ├── models/
│   │   ├── base.py          # Base, TimestampMixin
│   │   ├── user.py
│   │   ├── track.py
│   │   ├── album.py
│   │   ├── playlist.py
│   │   ├── like.py
│   │   ├── dislike.py
│   │   ├── follow.py
│   │   ├── lyrics.py
│   │   └── complaint.py
│   ├── repositories/        # DB access layer
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # Business logic
│   └── static/mini_app/     # Mini App (HTML/CSS/JS)
├── alembic/                  # Migrations (10 versions)
├── frontend/                 # React/Vite Mini App
├── scripts/                  # Operational helpers
├── tests/                    # pytest + anyio
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## Запуск локально

### 1. Первоначальная настройка
```bash
copy .env.example .env        # создать .env из шаблона
poetry install                 # установить зависимости
```

### 2. Инфраструктура (Docker)
```bash
docker compose up -d postgres minio redis
```

### 3. Миграции БД
```bash
poetry run alembic upgrade head
```

### 4. Бэкенд (терминал 1)
```bash
poetry run python main.py
```
API доступен на http://localhost:8000

### 5. Frontend / Mini App (терминал 2)
```bash
cd frontend
npm install
npm run dev
```
Mini App доступен на http://localhost:5173/mini_app/

### 6. Бот (отдельный репозиторий DotSoundBot, терминал 3)
```bash
cd C:\Users\User\PycharmProjects\DotSoundBot
python main.py
```

### Быстрый запуск через Makefile
```bash
make init    # первый раз: .env + docker + миграции
make dev     # инфра + миграции + бэкенд
make test    # тесты
make lint    # Ruff + Black + mypy
make format  # автоформатирование
```

### Для Telegram (HTTPS через ngrok)
```bash
ngrok http 5173
```
Полученный URL вписать в `.env` бота как `MINI_APP_URL`.
