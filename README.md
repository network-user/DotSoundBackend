# DotSound Backend

API-сервер музыкальной платформы DotSound — SoundCloud-style, UGC, без рекламы.
Хранит треки в MinIO, метаданные в PostgreSQL, раздаёт Telegram Mini App.

> Этот репозиторий опубликован как engineering showcase.
> Критичная закрытая логика выносится в приватный репозиторий
> `DotSoundPrivateCore`.

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| API | FastAPI 0.111 + uvicorn |
| БД | PostgreSQL 16 + SQLAlchemy 2 (async) |
| Хранилище | MinIO (S3-совместимое) |
| Миграции | Alembic |
| Зависимости | Poetry |
| Mini App | React 18 + Vite + TypeScript |

---

## Требования

| Инструмент | Версия | Зачем |
|-----------|--------|-------|
| Python | 3.11+ | Backend |
| [Poetry](https://python-poetry.org/) | любая | Управление зависимостями Python |
| Node.js | 18+ | Сборка React Mini App |
| npm | 9+ | Менеджер пакетов Node.js |
| Docker | любая | Запуск PostgreSQL и MinIO |
| Docker Compose | v2+ | Оркестрация контейнеров |

---

## Быстрый старт

### Шаг 1 — Клонируйте и установите зависимости

```bash
git clone <repo-url>
cd DotSoundBackend

poetry install
```

### Шаг 2 — Настройте переменные окружения

```bash
cp .env.example .env
```

Файл `.env` уже содержит корректные значения для локального запуска через Docker.
Если нужно изменить — откройте `.env` и отредактируйте нужные строки (см. раздел [Переменные окружения](#переменные-окружения)).

### Шаг 3 — Запустите инфраструктуру

```bash
docker compose up -d
```

Это поднимет:
- **PostgreSQL 16** на порту `5432` (user: `dotsound`, password: `dotsound`, db: `dotsound`)
- **MinIO** на порту `9000` (API) и `9001` (веб-консоль)

Проверить что контейнеры запущены:
```bash
docker compose ps
```

### Шаг 4 — Примените миграции базы данных

```bash
poetry run alembic upgrade head
```

### Шаг 5 — Запустите сервер

```bash
poetry run python main.py
```


```bash
# Разовый запуск (ручной триггер / тест)
poetry run python scripts/sc_id_refresher.py --now

# Запуск как демон (еженедельное обновление)
poetry run python scripts/sc_id_refresher.py

# Режим отладки
poetry run python scripts/sc_id_refresher.py --now --log-level DEBUG
```

**Docker Compose (по желанию):** тот же демон как отдельный контейнер. Поднимается
с профилем `sc-refresh` и пишет в смонтированный `.env` (после смены ключа
перезапустите `backend` вручную, как и при локальном демоне).

```bash
# Вместе со стеком
docker compose --profile sc-refresh up -d

# Только контейнер-обновляльщик (когда остальное уже поднято)
docker compose --profile sc-refresh up -d sc_id_refresher
```

Сервер запустится на `http://localhost:8000` с автоперезагрузкой (`reload=True`).

> **Swagger UI:** `http://localhost:8000/docs`

---

## Mini App (Frontend)

Mini App — это React-приложение, которое открывается как Telegram WebApp.
Исходный код находится в `frontend/`, сборка выводится в `app/static/mini_app/`.

### Разработка (hot reload)

```bash
cd frontend
npm install      # только при первом запуске
npm run dev
npm run dev -- --host # локальный запуск
```

Открыть: `http://localhost:5173/mini_app/`

API-запросы автоматически проксируются на `http://localhost:8000` — backend должен быть запущен.

### Production-сборка

```bash
cd frontend
npm run build
```

После сборки файлы попадают в `app/static/mini_app/` и автоматически раздаются FastAPI по адресу `http://localhost:8000/mini_app/`.

> Пересборка нужна после каждого изменения в `frontend/src/`.

---

## Переменные окружения

Файл: `.env` (создаётся из `.env.example`)

| Переменная | Описание | Значение по умолчанию |
|-----------|---------|----------------------|
| `DATABASE_URL` | asyncpg URL PostgreSQL | `postgresql+asyncpg://dotsound:dotsound@localhost:5432/dotsound` |
| `MINIO_ENDPOINT` | Адрес MinIO (host:port) | `localhost:9000` |
| `MINIO_ACCESS_KEY` | Логин MinIO | `minioadmin` |
| `MINIO_SECRET_KEY` | Пароль MinIO | `minioadmin` |
| `MINIO_BUCKET` | Имя бакета для аудио | `dotsound-audio` |
| `MINIO_USE_SSL` | Использовать HTTPS для MinIO | `false` |
| `LOG_LEVEL` | Уровень логов (`DEBUG`/`INFO`/`WARNING`) | `INFO` |
| `COMPLAINT_THRESHOLD` | Количество жалоб до авто-скрытия трека | `3` |

---

## API

| Метод | Путь | Описание |
|-------|------|---------|
| `GET` | `/api/v1/health` | Healthcheck |
| `POST` | `/api/v1/users` | Регистрация / обновление пользователя |
| `POST` | `/api/v1/tracks/upload` | Загрузить трек (multipart/form-data) |
| `GET` | `/api/v1/tracks` | Список треков / поиск (`?q=`, `?size=`, `?page=`) |
| `GET` | `/api/v1/tracks/{id}` | Получить трек по ID |
| `GET` | `/api/v1/tracks/{id}/stream` | Presigned URL для воспроизведения |
| `POST` | `/api/v1/tracks/{id}/play` | Увеличить счётчик прослушиваний |
| `POST` | `/api/v1/likes/{user_id}/{track_id}` | Поставить / снять лайк |
| `GET` | `/api/v1/likes/{user_id}` | Лайкнутые треки пользователя |
| `POST` | `/api/v1/complaints` | Подать жалобу на нарушение АП |
| `*` | `/api/v1/playlists/…` | CRUD плейлистов |

Полная документация с примерами запросов: `http://localhost:8000/docs`

---

## Жалобы (DMCA / ст. 1253.1 ГК РФ)

При достижении `COMPLAINT_THRESHOLD` жалоб трек автоматически скрывается (`is_active = false`).
Один пользователь может подать жалобу на конкретный трек только один раз.

---

## Структура проекта

```
DotSoundBackend/
├── app/
│   ├── api/v1/          # Маршруты (health, users, tracks, likes, complaints, playlists)
│   ├── core/            # БД, логирование, rate limiting, S3
│   ├── middlewares/     # Логирование запросов
│   ├── models/          # SQLAlchemy ORM модели
│   ├── repositories/    # Слой доступа к БД
│   ├── schemas/         # Pydantic схемы (запрос / ответ)
│   ├── services/        # Бизнес-логика
│   ├── static/mini_app/ # Собранный React Mini App (git-ignored)
│   └── main.py          # Фабрика FastAPI-приложения
├── frontend/            # Исходный код React Mini App
│   └── src/
├── alembic/             # Миграции БД
├── tests/
├── docker-compose.yml   # PostgreSQL + MinIO
├── .env.example
└── pyproject.toml
```

Приватное ядро, которое не публикуется в этом репозитории:

- `DotSoundPrivateCore` — internal auth policies, protected
  integration contracts, anti-abuse и другие production-only правила.

---

## Команды разработчика

```bash
# Тесты
poetry run pytest

# Линтер
poetry run ruff check .

# Проверка типов
poetry run mypy app/

# Форматирование
poetry run black app/

# Создать новую миграцию
poetry run alembic revision --autogenerate -m "описание изменений"

# Откатить последнюю миграцию
poetry run alembic downgrade -1
```

---

## License / Usage Restrictions

Репозиторий **не является open source**.

- Лицензия: [`LICENSE`](./LICENSE)
- Ограничения использования: [`NOTICE`](./NOTICE)

Разрешён просмотр и не-production оценка кода. Продакшн-использование,
коммерческая эксплуатация, SaaS-хостинг, встраивание в другие продукты
и перераспространение запрещены без письменного разрешения.

---

## Полезные ссылки при локальной разработке

| Сервис | URL |
|--------|-----|
| API (Swagger UI) | http://localhost:8000/docs |
| Mini App | http://localhost:8000/mini_app/ |
| Mini App (dev сервер) | http://localhost:5173/mini_app/ |
| MinIO веб-консоль | http://localhost:9001 (login: `minioadmin` / `minioadmin`) |

---

> Связанный репозиторий: [DotSoundBot](../DotSoundBot)
