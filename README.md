# DotSound Backend

API-сервер музыкальной платформы DotSound — SoundCloud-style, UGC, без рекламы.
Хранит треки в MinIO, метаданные в PostgreSQL, раздаёт Telegram Mini App.

> Source-available engineering showcase.
> Репозиторий открыт для чтения кода и оценки инженерных решений.
> Закрытое ядро `DotSoundPrivateCore` намеренно не публикуется и
> требуется только для полного локального запуска.

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
| Python | 3.12 | Backend |
| [Poetry](https://python-poetry.org/) | любая | Управление зависимостями Python |
| Node.js | 18+ | Сборка React Mini App |
| npm | 9+ | Менеджер пакетов Node.js |
| Docker | любая | Запуск PostgreSQL и MinIO |
| Docker Compose | v2+ | Оркестрация контейнеров |

---

## Быстрый старт

Этот раздел описывает локальный запуск для владельцев полного
DotSound-workspace. Публичный showcase-клон без соседнего приватного
`DotSoundPrivateCore` предназначен для code review и изучения
архитектуры, а не для самостоятельного production/development запуска.

### Шаг 1 — Клонируйте и установите зависимости

```bash
git clone <repo-url>
cd DotSoundBackend

# Требуется соседний приватный пакет ../DotSoundPrivateCore.
poetry install
```

### Шаг 2 — Настройте переменные окружения

```bash
cp .env.example .env
```

Файл `.env.example` документирует переменные для локальной среды.
Не используйте dev-значения как production-конфигурацию.

### Шаг 3 — Запустите инфраструктуру

```bash
docker compose up -d
```

Это поднимет локальные dev-сервисы: PostgreSQL, Redis, MinIO и
другие компоненты, если они включены в compose-профилях.

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

**Docker Compose (по желанию, dev):** дополнительные фоновые сервисы
включаются compose-профилями. Они оставлены как пример production-like
оркестрации, но не являются частью публичного standalone-дистрибутива.

```bash
# Локально / dev — вместе со стеком
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
| Переменная | Описание |
|-----------|---------|
| `DATABASE_URL` | asyncpg URL PostgreSQL |
| `REDIS_URL` | Redis для rate limit, очередей и realtime |
| `MINIO_*` | S3-совместимое хранилище для медиа |
| `JWT_SECRET` | Секрет подписи JWT; обязателен для non-debug запуска |
| `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` | HTTP/CORS guardrails |
| `ADMIN_PANEL_PATH` | Slug админ-панели и admin API |

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

Локальная OpenAPI-документация доступна в dev-режиме по адресу
`http://localhost:8000/docs`. Для публичной эксплуатации схему и
internal routes нужно закрывать настройками окружения и периметра.

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

- `DotSoundPrivateCore` — закрытые правила и decision-функции.
  Публичный Backend показывает транспортный слой, API, хранение,
  orchestration и frontend, но не раскрывает реализацию ядра.

---

## Команды разработчика

Команды ниже отражают полный internal workspace. В публичном showcase
они полезны как ориентир, но могут требовать закрытый пакет
`DotSoundPrivateCore` и актуальную локальную инфраструктуру. На момент
публикационной подготовки полный Ruff/Mypy backlog не заявляется как
зелёный quality gate; активные обязательные guardrails находятся в
`.github/workflows/policy-guardrails.yml`.

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

Репозиторий **не является open source**. Это source-available showcase:
код можно читать и оценивать, но права на production-использование,
hosting, redistribution и производные продукты ограничены лицензией.

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
