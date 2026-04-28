# Покрытие Backend API клиентом Mini App и админки

Документ фиксирует разрыв между эндпоинтами FastAPI и использованием во
frontend. Обновлять при добавлении крупных фич API или экранов.

## Источник клиента

- Mini App: [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts)
- Админка: [`frontend/src/admin/lib/adminApi.ts`](../frontend/src/admin/lib/adminApi.ts)

## Цель следующего PR по клиенту (расширение `api.ts` + точечный UI)

После применения патча к клиенту должны появиться обёртки и правки ниже.

### Обёртки в `api.ts`

- Учётная запись: `DELETE /users/me`, `POST /users/me/restore`, лента
  `GET /users/me/feed`, списки `GET /users/{id}/followers|following`.
- `GET /metadata/genres` — популярные жанры платформы (отдельно от
  `/tracks/genres` в онбординге).
- Связанные аккаунты: `DELETE /linked-accounts/{provider}`, `GET
  .../{provider}/playlists`.
- Плейлисты: `PUT`/`DELETE` плейлиста, `DELETE` трека из плейлиста,
  инвайты коллаборации и accept.
- Альбомы: полный CRUD и операции с треками в альбоме.
- Чаты (группы): `POST/DELETE .../chats/{id}/members`.
- Артисты: `GET /artists/{id}/similar`.
- Co-listen: REST для комнаты (WS отдельно).

### Исправление бага

- Загрузка аватара: использовать `POST /api/v1/users/me/avatar` (не
  `POST /users/{id}/avatar` — такого POST на бэкенде нет).

### Точечный UI

- Настройки: блок OAuth (Spotify / VK / SoundCloud) — отключение связи;
  опасная зона удаления аккаунта с подтверждением словом `DELETE`.
- Карточка артиста: блок «Похожие» по `/artists/{id}/similar`.
- Админка: `GET /admin/metrics/instant` — `adminApi.metricInstant`.

### Очередь без клиентских обёрток в первой итерации

То, что остаётся на потом (есть на бэкенде, нужны экраны или отдельная
задача):

| Область | Заметка |
|--------|---------|
| Альбомы | Полноценный UX после появления методов в `api.ts`. |
| Co-listen | REST + WebSocket, отдельный продуктовый экран. |
| Лента подписок | Вкладка / секция на `GET /users/me/feed`. |
| Подписчики / подписки | Списки в профиле автора. |
| Восстановление аккаунта | UI после того, как профиль начнёт отдавать признак pending deletion. |
| Плейлисты | Добавить трек из карточки; редактирование; коллаборации. |
| Импорт | Выбор плейлиста провайдера через `.../playlists`. |
| Чаты | UI состава группы. |

## Не цель Mini App

- `/api/v1/internal/*` — воркеры (ComputeWorker и др.).
- Служебные `/health/*`, debug `GET /search/_admin/reindex`.

## DotSoundBot

Бот использует узкий HTTP-клиент; отличие набора эндпоинтов от Mini App
ожидаемо.
