# DotSound Backend

API-сервер музыкальной платформы DotSound — SoundCloud-style, UGC, без рекламы.
Хранит треки в MinIO, метаданные в PostgreSQL, отдаёт Mini App.

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| API | FastAPI 0.111 + uvicorn |
| БД | PostgreSQL 16 + SQLAlchemy 2 async |
| Хранилище | MinIO (S3-совместимое) |
| Миграции | Alembic |
| Зависимости | Poetry |
| Mini App | React 18 + Vite + TypeScript |

---

## Требования

- Python 3.11+, [Poetry](https://python-poetry.org/)
- Node.js 18+, npm
- Docker & Docker Compose

---

## Быстрый старт

```bash
# 1. Зависимости
poetry install

# 2. Конфиг
cp .env.example .env
# DATABASE_URL, MINIO_* — заполнены для docker-compose по умолчанию

# 3. Инфраструктура (PostgreSQL + MinIO)
docker compose up -d

# 4. Миграции
poetry run alembic upgrade head

# 5. Запуск
poetry run python main.py
# → http://localhost:8000
```

### Frontend (Mini App)

**Разработка** — hot reload, API проксируется на `localhost:8000`:

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173/mini_app/
```

**Production-сборка** — выводит в `app/static/mini_app/`, раздаётся FastAPI:

```bash
cd frontend
npm run build
# → http://localhost:8000/mini_app/
```

---

## API

| Метод | Путь | Описание |
|-------|------|---------|
| `GET` | `/api/v1/health` | Healthcheck |
| `POST` | `/api/v1/users` | Регистрация пользователя |
| `POST` | `/api/v1/tracks/upload` | Загрузить трек (multipart) |
| `GET` | `/api/v1/tracks` | Список / поиск треков |
| `GET` | `/api/v1/tracks/{id}/stream` | Presigned URL для воспроизведения |
| `POST` | `/api/v1/tracks/{id}/play` | Увеличить счётчик прослушиваний |
| `POST` | `/api/v1/likes/{user_id}/{track_id}` | Поставить / снять лайк |
| `GET` | `/api/v1/likes/{user_id}` | Лайкнутые треки |
| `POST` | `/api/v1/complaints` | Подать жалобу (DMCA / ст. 1253.1 ГК РФ) |
| `GET` | `/api/v1/complaints/{track_id}` | Список жалоб на трек |
| `*` | `/api/v1/playlists/…` | CRUD плейлистов |

Swagger UI: `http://localhost:8000/docs`

---

## Жалобы (DMCA / ст. 1253.1 ГК РФ)

При `COMPLAINT_THRESHOLD` (по умолчанию **3**) жалобах трек автоматически скрывается (`is_active = false`).
Каждый пользователь может подать жалобу на трек только один раз.

---

## Проверка

```bash
# Тесты
poetry run pytest

# Линтер / типы
poetry run ruff check .
poetry run mypy app/
```

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|---------|-------------|
| `DATABASE_URL` | asyncpg URL PostgreSQL | — |
| `MINIO_ENDPOINT` | Адрес MinIO | `localhost:9000` |
| `MINIO_ACCESS_KEY` | Ключ доступа | `minioadmin` |
| `MINIO_SECRET_KEY` | Секрет | `minioadmin` |
| `MINIO_BUCKET` | Бакет | `dotsound-audio` |
| `MINIO_USE_SSL` | HTTPS для MinIO | `false` |
| `LOG_LEVEL` | Уровень логов | `INFO` |
| `COMPLAINT_THRESHOLD` | Жалоб до скрытия трека | `3` |

---

## Архитектура

```
api/v1/ → services/ → repositories/ → models/
schemas/ ←→ api/ и services/
S3: app/core/s3.py
БД: app/core/db.py
```

> Связанный репозиторий: [DotSoundBot](../DotSoundBot)
