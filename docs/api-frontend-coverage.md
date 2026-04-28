# Покрытие Backend API клиентом Mini App и админки

Документ фиксирует разрыв между эндпоинтами FastAPI и клиентом. Обновлять
при добавлении крупных фич API или экранов.

## Продуктовый приоритет закрытия разрывов

1. **Плейлисты и альбомы** — основной пользовательский контент библиотеки:
   методы в [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts); UX
   редактирования / «добавить в плейлист» из карточки трека — в backlog
   ниже.
2. **Аккаунт и связанные OAuth-аккаунты** — настройки: отключение импорта
   (Spotify / VK / SoundCloud), удаление аккаунта с подтверждением `DELETE`.
3. **Co-listen** — REST обёртки есть; отдельный экран + WebSocket — позже.
4. **Лента подписок и списки подписчиков** — методы в `api.ts`; отдельные
   экраны — позже.

## Источник клиента

- Mini App: [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts)
- Админка: [`frontend/src/admin/lib/adminApi.ts`](../frontend/src/admin/lib/adminApi.ts)

## Реализовано в клиенте (`api.ts`)

- Учётная запись: `requestAccountDeletion`, `restoreAccountAfterDeletion`,
  `getFollowingFeed`, `listFollowers`, `listFollowingUsers`.
- `getPopularPlatformGenres` — `GET /metadata/genres`.
- Связанные аккаунты: `disconnectLinkedAccount`,
  `getLinkedProviderPlaylists`.
- Плейлисты: `getPlaylists` / `createPlaylist` (без лишнего `owner_id`),
  `updatePlaylist`, `deletePlaylist`, `addTrackToPlaylist` (опционально
  `position`), `removeTrackFromPlaylist`, `createPlaylistInvite`,
  `acceptPlaylistInvite`.
- Альбомы: `listUserAlbums`, `createAlbum`, `getAlbum`, `updateAlbum`,
  `deleteAlbum`, `addTrackToAlbum`, `removeTrackFromAlbum`.
- Чаты: `addChatMember`, `removeChatMember`.
- Co-listen REST: `createColistenRoom`, `getColistenRoom`,
  `patchColistenRoom`.
- Артисты: `listSimilarCatalogArtists`.

### Исправление

- Загрузка аватара: `uploadAvatar(formData)` → `POST /users/me/avatar`.

### Типы

- См. [`frontend/src/types/api.ts`](../frontend/src/types/api.ts):
  `FollowListResponse`, `LinkedPlaylistsResponse`, `PlaylistInviteOut`,
  `AlbumRecord`, `AlbumWithTracksRecord`, `ColistenRoomState`,
  `ArtistListPayload`.

## UI

- Настройки: [`OAuthImportAccounts.tsx`](../frontend/src/components/Settings/OauthImportAccounts.tsx),
  [`AccountDangerZone.tsx`](../frontend/src/components/Settings/AccountDangerZone.tsx).
- Карточка артиста: блок «Похожие» — [`ArtistView.tsx`](../frontend/src/components/ArtistView/ArtistView.tsx).
- Админка: `adminApi.metricInstant` — для опционального вывода на экране
  метрик.

## Backlog (методы есть, UX позже)

| Область | Заметка |
|--------|---------|
| Альбомы | Полноценные экраны каталога альбомов. |
| Co-listen | Продуктовый экран + WS. |
| Лента подписок | Вкладка на `getFollowingFeed`. |
| Подписчики / подписки | Списки в профиле автора. |
| Восстановление аккаунта | UI после признака pending deletion в профиле. |
| Плейлисты | Добавить трек из карточки; редактирование; коллаборации. |
| Импорт | Выбор плейлиста провайдера. |
| Чаты | UI состава группы. |

## Регрессия покрытия

- Скрипт: [`scripts/check_openapi_frontend_coverage.py`](../scripts/check_openapi_frontend_coverage.py).

## Не цель Mini App

- `/api/v1/internal/*`, `/health/*`, debug `GET /search/_admin/reindex`.

## DotSoundBot

Бот использует узкий HTTP-клиент; меньший набор эндпоинтов ожидаем.
