Ты — агент в чате, отвечаешь за поток E iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: TrackCard, TrackList, TrackCardSheet, ChatsView, ChatView

Карточка трека — центральный «атом» UI, она везде. Ты отвечаешь за её визуальный язык, list-варианты с swipe-actions, long-press, beat-pulse на играющем. И отдельно — чат-экраны (community feed как iMessage).

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты: `lib/motion.ts`, `lib/island.ts`, `lib/coverPalette.ts`.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang, референс — iOS 18 + visionOS Liquid Glass + iMessage.

## Обязательно прочитать

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-E-tracks-chat.md`
4. `docs/design-system.md`

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром.
4. Тема — dark only.
5. Без эмодзи (включая reactions — используем монохром-иконки).
6. `prefers-reduced-motion: reduce` уважать (beat-pulse, swipe rubber-band, scale).
7. PrivateCore-внутренности не упоминать.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. `TODO(redesign-2026)` если поля нет.
9. Conventional Commits, scope = `redesign-e`.

## Твои файлы

```
frontend/src/components/TrackCard/TrackCard.tsx
frontend/src/components/TrackCard/TrackCardSheet.tsx
frontend/src/components/TrackList/TrackList.tsx (+ подкомпоненты, если есть)
frontend/src/views/ChatsView.tsx
frontend/src/views/ChatView.tsx
frontend/src/components/Chat/** (если существует)
frontend/src/styles/redesign-tracks.css
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.tracks.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.tracks.*)
```

## NO-TOUCH

```
frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
frontend/src/main.tsx, App.tsx
frontend/src/locales/ru.json, en.json, i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/** (Stage-A)
frontend/src/components/BottomNav/**, Auth/**, Onboarding/** (Stage-B)
frontend/src/views/HomeView, DailyMixView, WeeklyMixView, RadioView, NotFoundView, etc. (Stage-C)
frontend/src/views/SearchView, LibraryView, LikedView, PlaylistsView, ProfileView (Stage-D)
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css
frontend/src/components/ui/* (Stage-0)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### TrackCard

- Два варианта вёрстки: `compact` (узкая строка для списков), `expanded` (большая карточка для grid).
- Обёртка — `<MotionPress variant="subtle">`.
- Cover — `<SharedCover trackId={track.id}>` для shared-element transition с PlayerBar.
- Если `isCurrent && isPlaying` — обернуть мини-обложку в `<BeatPulse bpm={track.bpm ?? 120} active>`.
- На long-press через `<LongPressMenu items={[...]}>` показывать meню: Like / Add to playlist / Add to queue / Share / Hide / Report.
- Like-action — `<MorphIcon name="heart" filled={liked}>` через `<MotionPress variant="icon">` со spring.

### TrackList

- Каждый row обёрнут в `<SwipeRow>`:
  - default: `leftAction={{ icon: 'heart', label: 'Лайк' }}`, `rightAction={{ icon: 'queue', label: 'В очередь' }}`.
  - в LikedView (если list получает prop `flavor="liked"`) `leftAction.icon='heart-fill'` + опция «Снять лайк».
- Текст «Сейчас играет» в left-region row → морф-индикатор `<BeatPulse>` вместо статической иконки.

### TrackCardSheet

- Bottom-sheet с большой обложкой через `<KenBurnsCover>` поверх `<AmbientStage>`.
- Внутри — секции: основные действия (`<MotionPress variant="primary">` на Play, ghost на Add to queue/Like/Share), метаданные, lyrics-preview.
- Закрытие через drag-down: `m.div drag="y" dragConstraints={{ top: 0, bottom: 0 }}`, на dragEnd > 100 px — close.

### ChatsView (список чатов)

- Каждый чат — row с аватаркой и preview message. Обёртка — `<SwipeRow>`:
  - `leftAction = { icon: 'pin', label: 'Закрепить' }`,
  - `rightAction = { icon: 'archive', label: 'В архив' }`.
- Long-press → `<LongPressMenu>` с действиями (Mute / Pin / Mark unread / Delete).
- Sticky-header с большим заголовком «Чаты» (large-title `--fs-lt`).

### ChatView

- Header с аватаром собеседника, sticky-blur-фон.
- Сообщения — bubble в стиле iMessage:
  - own — alignSelf: flex-end, ярко-серый-фон;
  - peer — alignSelf: flex-start, прозрачный glass-фон.
  - Без цветных bubble — строго монохром.
- На отправку нового сообщения — bubble «прилетает» через `m.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}` со spring. На входящее — fade-up.
- Reactions: long-press на bubble → `<LongPressMenu items=[heart, fire, lol, sad, angry, dotsound]>`. Все иконки — монохромные `<MorphIcon>` (не emoji).
- Composer:
  - Input в capsule glass-medium.
  - Send button — `<MotionPress variant="primary">` с `<MorphIcon name="arrow-up" filled />`. На press — spring scale.

### CSS

Все стили — `frontend/src/styles/redesign-tracks.css`. Префиксы: `.re-tc-`, `.re-tl-`, `.re-tcs-`, `.re-chats-`, `.re-chat-`, `.re-bubble-`.

### i18n

Только `i18n_extra2_*.json` под `redesign.tracks.*`.

## Acceptance criteria

- [ ] TrackCard: compact + expanded, SharedCover, BeatPulse на играющем, long-press menu.
- [ ] TrackList: каждый row — SwipeRow с настроенными action'ами.
- [ ] TrackCardSheet: KenBurns + AmbientStage, drag-down to close.
- [ ] ChatsView: rows с swipe и long-press.
- [ ] ChatView: монохром-bubbles, spring анимация прилёта, monochrome reactions.
- [ ] reduced-motion корректен (beat-pulse выключен, scale-эффекты выключены, KenBurns статичен).
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. По одному коммиту на компонент.
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Conventional Commits, scope `redesign-e`. Примеры:
   - `feat(redesign-e): rebuild TrackCard with shared cover and beat pulse`
   - `feat(redesign-e): swipe-actions and long-press on TrackList rows`
   - `feat(redesign-e): TrackCardSheet with ambient stage and drag-to-close`
   - `feat(redesign-e): iMessage-style ChatView with monochrome reactions`
   - `feat(redesign-e): chats list with swipe and long-press`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
