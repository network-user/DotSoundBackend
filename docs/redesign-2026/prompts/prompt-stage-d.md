Ты — агент в чате, отвечаешь за поток D iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: Library, Search, Liked, Playlists, Profile, Settings

«Библиотечная» сторона приложения — там, где пользователь живёт после первой сессии. Большие чистые списки, sticky-headers с blur, шёлковые табы, swipe-actions на rows, профиль с большим аватаром.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives в `frontend/src/components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты: `lib/motion.ts`, `lib/island.ts`, `lib/coverPalette.ts`.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang, референс — iOS 18 + visionOS Liquid Glass + Apple Music.

## Обязательно прочитать

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-D-library.md`
4. `docs/design-system.md`

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром.
4. Тема — dark only.
5. Без эмодзи.
6. `prefers-reduced-motion: reduce` уважать.
7. PrivateCore-внутренности не упоминать.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. `TODO(redesign-2026)` + заглушка если поля нет.
9. `TrackCard` и `TrackList` — owned by Stage-E. Можешь их **использовать** как есть и **обернуть** в `SwipeRow` / `m.div` снаружи, но **не редактировать их внутренности**.
10. Conventional Commits, scope = `redesign-d`.

## Твои файлы

```
frontend/src/views/SearchView.tsx
frontend/src/views/LibraryView.tsx
frontend/src/views/LikedView.tsx
frontend/src/views/PlaylistsView.tsx
frontend/src/views/ProfileView.tsx
frontend/src/components/Settings/**
frontend/src/components/Profile/**
frontend/src/styles/redesign-library.css
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.library.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.library.*)
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
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css
frontend/src/components/ui/* (Stage-0)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### SearchView

- Sticky-header с большим search input — capsule, `glass--medium`. Focus растягивает поле через `m.input animate={{ scaleX: 1.02 }}` (или контейнерный wrapper).
- Под input — chips-фильтры (треки / артисты / альбомы / плейлисты / внешние). Активный → filled `<MorphIcon>`. Все chips — `<MotionPress>`.
- Результаты — секции (треки, артисты, альбомы, плейлисты, внешние). Каждая секция — `m.div variants={VARIANTS_FADE_UP}` со staggered delay.
- Прогрессивная выдача (внешние подгружаются после) — уже работает в коде, не ломай. Только визуальный polish.

### LibraryView

- Capsule-tabs вверху. Заменить статичный indicator на `<m.span layoutId="lib-tab-indicator">` с `transition={SPRING_LAYOUT}` под активным.
- Внутри каждой вкладки — список с rows, обёрнутыми в `<SwipeRow>`:
  - Liked: `leftAction = { icon: 'heart', label: 'Снять лайк', destructive: false }`, `rightAction = { icon: 'queue', label: 'В очередь' }`.
  - Playlists: `leftAction = { icon: 'play', label: 'В плеер' }`, `rightAction = { icon: 'trash', label: 'Удалить', destructive: true }`.
  - Mine: либо без swipe, либо `rightAction = { icon: 'share', label: 'Поделиться' }`.

### LikedView

- Sticky-header с metadata: «N лайков · последний M назад» + sort controls (newest/oldest/by artist) — `<MotionPress>` chips.
- TrackList снизу (используешь существующий компонент). Каждый row обёрнут в `<SwipeRow>`.

### PlaylistsView

- Grid 2-col больших обложек плейлистов. Long-press через `<LongPressMenu>` — items: Переименовать / Дублировать / Удалить.
- На клик — переход (как было).

### ProfileView

- Hero: большой аватар (128 px) в круге. KenBurnsCover на абстрактной градиентной подложке монохрома как фон.
- Имя — large-title (`--fs-lt`).
- Секции (Stats, My tracks, My playlists, Followed artists) — карточки `glass--medium` с `<MotionPress>` для входа.
- Кнопка «Поделиться профилем» — `<MotionPress variant="ghost">`.

### Settings

- Если уже `Sheet` — оставь его, только обнови содержимое.
- Каждая секция — карточки с `<MotionPress>` rows.
- Toggles — кастомный `<m.button>` с двух-состоянным `whileTap` (capsule scale).
- Haptic на каждое значимое действие (используй `hapticTick` из `lib/telegram` для тиков, `haptic('light')` для toggle).
- Подключить `<DynamicIsland>` для подтверждений сохранения (вместо мелких toast'ов): `showIsland({ kind: 'toast', title: 'Сохранено', durationMs: 2000 })`.

### CSS

Все стили — `frontend/src/styles/redesign-library.css`. Префиксы: `.rd-search-`, `.rd-lib-`, `.rd-liked-`, `.rd-pl-`, `.rd-profile-`, `.rd-settings-`.

### i18n

Только `i18n_extra2_*.json` под `redesign.library.*`.

## Acceptance criteria

- [ ] SearchView: capsule input с focus-spring, chips-фильтры с MorphIcon, staggered секции.
- [ ] LibraryView: layoutId-индикатор табов.
- [ ] LikedView/PlaylistsView: rows со swipe-actions.
- [ ] PlaylistsView: long-press → context-menu.
- [ ] ProfileView: hero с KenBurns на градиенте + большие секции glass-medium.
- [ ] Settings: toggle-anim, DynamicIsland confirm.
- [ ] reduced-motion корректен.
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. По одному коммиту на view/секцию.
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Conventional Commits, scope `redesign-d`. Примеры:
   - `feat(redesign-d): polish SearchView with capsule input and morph filters`
   - `feat(redesign-d): rebuild LibraryView tabs with layout indicator`
   - `feat(redesign-d): swipe-actions on Liked and Playlists rows`
   - `feat(redesign-d): refresh ProfileView hero with KenBurns avatar bg`
   - `feat(redesign-d): settings rebuilt with motion primitives and island confirms`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
