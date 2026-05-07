Ты — агент в чате, отвечаешь за поток F iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: Artist, Album, Playlist, Genre, External Track / Album

Карточки артиста и альбома — апекс-эстетика проекта. Большой parallax-постер, KenBurns на ambient-фоне, секции со staggered reveal. Списки треков подключаются через owned-Stage-E компоненты.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты: `lib/motion.ts`, `lib/island.ts`, `lib/coverPalette.ts`.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang, референс — iOS 18 + visionOS Liquid Glass + Apple Music карточка артиста.

## Обязательно прочитать

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-F-artist.md`
4. `docs/design-system.md`
5. `AGENTS.md` (раздел Source attribution исключение — для карточки артиста разрешён `source_name` / `source_page_url`)

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром.
4. Тема — dark only.
5. Без эмодзи.
6. `prefers-reduced-motion: reduce` уважать (parallax, KenBurns).
7. PrivateCore-внутренности (имена стадий, веса, моделей, провайдеров) **не упоминать**. На карточке артиста разрешено показывать только публичные `source_name` и `source_page_url` из API.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. `TODO(redesign-2026)` если поля нет.
9. `TrackCard` / `TrackList` — Stage-E. Используй как есть, **не редактируй**.
10. Conventional Commits, scope = `redesign-f`.

## Твои файлы

```
frontend/src/views/ArtistView.tsx
frontend/src/views/AlbumView.tsx
frontend/src/views/PlaylistView.tsx
frontend/src/views/GenreView.tsx
frontend/src/views/ExternalTrackView.tsx
frontend/src/views/ExternalAlbumView.tsx
frontend/src/components/Artist/** (если есть)
frontend/src/components/Album/** (если есть)
frontend/src/styles/redesign-artist.css
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.artist.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.artist.*)
```

## NO-TOUCH

```
frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
frontend/src/main.tsx, App.tsx
frontend/src/locales/ru.json, en.json, i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/components/TrackCard/**, TrackList/**, TrackCardSheet/** (Stage-E)
frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/** (Stage-A)
frontend/src/components/BottomNav/**, Auth/**, Onboarding/** (Stage-B)
frontend/src/views/HomeView, DailyMix*, Radio* etc. (Stage-C)
frontend/src/views/SearchView, LibraryView, LikedView, PlaylistsView, ProfileView (Stage-D)
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css
frontend/src/components/ui/* (Stage-0)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### ArtistView

- Header (Apple Music-style):
  - Hero: большой `<KenBurnsCover>` поверх `<AmbientStage coverUrl={...}>`.
  - Sticky-blur при скролле — реализуй через `useScroll` + `useTransform` (mask с blur), либо CSS-only fallback `position: sticky` + `backdrop-filter`.
  - Имя — `--fs-lt` large-title.
  - Под ним — Followers count, Source name (если есть `source_name`/`source_page_url` из API — показать как ссылку на `<MotionPress variant="ghost">`).
- Action row: Play / Shuffle / Follow (`<MotionPress>` + `<MorphIcon>`). Follow toggles между outline и filled.
- Секции с staggered fade-up:
  - Top tracks (TrackList).
  - Albums (`<HorizontalSnap parallax>`).
  - Artist info (текстовый блок).
  - Similar artists (если есть в API) — `<HorizontalSnap>`.
- Внизу — `<MotionPress variant="ghost">` для Report / Open external (если есть source).

### AlbumView

- Header: hero обложка с KenBurns + AmbientStage.
- Под header — TrackList (используешь Stage-E компонент).
- Action row: Play all / Shuffle / Like / Add to library.

### PlaylistView

- Header: collage из 4 обложек (mosaic 2×2) + KenBurnsCover + AmbientStage.
- Description, owner-info, follower count.
- Action row: Play / Shuffle / Follow / Edit (если owner).
- TrackList со swipe-actions (компонент Stage-E уже умеет).

### GenreView

- Header: декоративный fullscreen градиент (монохром, разные тоны серого) + KenBurns на текстуре.
- Внутри — табы (Top tracks / New / Artists). Activate-indicator через `<m.span layoutId="genre-tab-indicator">` со spring layout.

### ExternalTrackView / ExternalAlbumView

- Header: hero обложка + KenBurns + AmbientStage.
- Бейдж `external` / `licensed` — pill `glass--medium` с outline-иконкой `link-external`.
- Source attribution — `<MotionPress variant="ghost">` на `source_page_url` (открывает в Telegram WebView через `window.Telegram.WebApp.openLink`).
- Контент: метаданные + Play CTA.
- Если у трека есть Lyrics — кнопка «Открыть текст», которая открывает `<FullscreenLyrics>`/`<TrackCardSheet>` (компоненты Stage-A/E).

### CSS

Все стили — `frontend/src/styles/redesign-artist.css`. Префиксы: `.rf-artist-`, `.rf-album-`, `.rf-playlist-`, `.rf-genre-`, `.rf-external-`.

### i18n

Только `i18n_extra2_*.json` под `redesign.artist.*`.

## Acceptance criteria

- [ ] ArtistView: hero с KenBurns + AmbientStage + sticky-blur header.
- [ ] AlbumView: hero + TrackList + action-row.
- [ ] PlaylistView: collage hero (4-обложечный) + TrackList со swipe.
- [ ] GenreView: fullscreen monochrome gradient + layoutId табов.
- [ ] ExternalTrack/AlbumView: external/licensed бейдж + source attribution через MotionPress.
- [ ] reduced-motion корректен.
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.
- [ ] Нет упоминаний внутренних компонентов PrivateCore (стадий, моделей, провайдеров) ни в коде, ни в комментариях.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. По одному коммиту на view.
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Conventional Commits, scope `redesign-f`. Примеры:
   - `feat(redesign-f): cinematic ArtistView with sticky-blur header and ambient hero`
   - `feat(redesign-f): rebuild AlbumView with KenBurns hero and action row`
   - `feat(redesign-f): playlist hero with mosaic cover collage`
   - `feat(redesign-f): GenreView monochrome scene with tab indicator`
   - `feat(redesign-f): external track/album view with attribution links`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
