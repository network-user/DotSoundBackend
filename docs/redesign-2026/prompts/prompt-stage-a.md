Ты — агент в чате, отвечаешь за поток A iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026` — primitives, токены, библиотеки и роуты-stub уже на месте.

## Твоя зона: Player Stack

PlayerBar (мини), Now Playing (полный экран), Fullscreen Lyrics, очередь, эквалайзер. Это «лицо» взаимодействия с музыкой — должно ощущаться на уровне Apple Music.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Уже есть готовые primitives в `frontend/src/components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты в `frontend/src/lib/`: `motion.ts` (spring presets, varianты, реэкспорт `m`), `island.ts` (`showIsland`, `dismissIsland`), `coverPalette.ts`.

Владелец принял решения: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang в одной ветке, референс — iOS 18 + visionOS Liquid Glass + Apple Music Now Playing.

## Обязательно прочитать перед началом

В строгом порядке:
1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-A-player.md`
4. `docs/design-system.md` (раздел Redesign 2026 primitives)

## Жёсткие правила

1. Только `frontend/`. Не трогаешь `app/`, `alembic/`, `dotsound_private_core/`, `bot/`, любые compute-worker.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром.
4. Тема — dark only.
5. Без эмодзи в UI и коммитах.
6. `prefers-reduced-motion: reduce` уважать везде (spring выключать, Ken Burns статичен).
7. Никаких упоминаний внутренних провайдеров и моделей PrivateCore.
8. Не правишь `lib/api.ts`, `types/api.ts`, `store/**`. Если нужны новые поля — `TODO(redesign-2026)` и заглушка.
9. Conventional Commits, scope = `redesign-a`.

## Твои файлы (можешь править ТОЛЬКО их)

```
frontend/src/components/PlayerBar/PlayerBar.tsx
frontend/src/components/FullscreenLyrics/FullscreenLyrics.tsx
frontend/src/components/FullscreenLyrics/* (если есть подкомпоненты)
frontend/src/components/QueueSheet/QueueSheet.tsx
frontend/src/components/Equalizer/Equalizer.tsx
frontend/src/views/NowPlayingView.tsx (заменить stub на полную реализацию)
frontend/src/styles/redesign-player.css
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.player.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.player.*)
```

## NO-TOUCH (нельзя трогать ни при каких условиях)

```
frontend/src/lib/api.ts
frontend/src/types/api.ts
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/store/**
frontend/src/hooks/**
frontend/src/locales/ru.json
frontend/src/locales/en.json
frontend/src/locales/i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/styles/tokens.css
frontend/src/styles/global.css
frontend/src/styles/components.css
frontend/src/styles/animations.css
frontend/src/styles/redesign-shared.css
frontend/src/components/ui/* (все primitives)
frontend/src/lib/motion.ts
frontend/src/lib/island.ts
frontend/src/lib/coverPalette.ts
docs/redesign-2026/**
любые файлы вне твоего Owned-списка
```

Если файла нет в Owned, но кажется нужно его поправить — это сигнал, что что-то не так. Останови работу и подними вопрос владельцу.

## Что сделать

### PlayerBar v3

- Вид: Liquid Glass (`.glass--liquid`), ambient-glow от текущей обложки (через `<AmbientStage>` или ручной gradient), beat-pulse на иконке Play, scrub с rubber-band overscroll.
- Все кнопки → `<MotionPress>`.
- Play/Pause → `<MorphIcon name="play" filled={isPlaying}>`.
- Like → `<MorphIcon name="heart" filled={liked}>`.
- Полосу обернуть в `<BeatPulse bpm={120} active={isPlaying}>` или применить точечно к иконке Play.
- Мини-обложка → `<SharedCover trackId={trackId} src={cover_url}>` (для shared-element transition в Now Playing).
- Прогресс-бар: при touch-down — расширяется через `m.div whileTap={{ scaleY: 1.5 }}`.

### NowPlayingView (полный экран)

Реализовать `frontend/src/views/NowPlayingView.tsx`. Открывается по свайпу-вверх с PlayerBar. На роуте `/now-playing` (он уже зарегистрирован Stage-0).

Структура:
- Фон — `<AmbientStage coverUrl={track.cover_url}>` + `<KenBurnsCover>` поверх.
- В верхней части — `<MotionPress variant="icon">` с chevron-down для закрытия.
- По центру — большая обложка через `<SharedCover trackId={track.id}>` (layout-shared с PlayerBar).
- Под обложкой — метаданные (title, artist), скруббер, контролы (prev / play / next + like + share). Все на `MotionPress` + `MorphIcon`.
- Три таба сегментированным контролом: **Now Playing**, **Lyrics**, **Queue**. Lyrics рендерит `<FullscreenLyrics inline />`. Queue рендерит `<QueueSheet inline />` (или контент очереди).
- Жест swipe-down закрывает: `m.section drag="y" dragConstraints={{top:0,bottom:0}}` + `onDragEnd` с порогом 120 px → `navigate(-1)`.
- Like-burst spring + scale.

### FullscreenLyrics

Apple Music лейаут: маленькая обложка слева, контролы справа в верхней части. Большая часть экрана — текст с line-by-line follow. Активная строка — `m.span layout` со spring. Beat-pulse на маленькой обложке.

### QueueSheet

- Обёртка `m.div` с `VARIANTS_SHEET_SLIDE_UP` slide-up.
- Каждый ряд очереди — обернуть в `<SwipeRow rightAction={{icon:'trash', label:'Удалить', onTrigger, destructive: true}}>`. Клик — играет трек (как было).
- На текущем играющем треке — beat-pulse-индикатор вместо queue-eq бар.

### Equalizer

- Bottom-sheet `m.div drag="y"` с drag-down для закрытия.
- Слайдеры со spring-pop при изменении (масштабирование thumb через `whileTap`).
- Toggle-pill для включения/выключения через `<MotionPress>`.

### CSS

Все стили — в `frontend/src/styles/redesign-player.css`. Префиксы классов: `.rp-player-`, `.rp-now-`, `.rp-queue-`, `.rp-eq-`. Никаких глобальных утилитарных классов.

### i18n

Новые ключи добавляй ТОЛЬКО в `i18n_extra2_ru.json` и `i18n_extra2_en.json` под namespace `redesign.player.*`. Не трогай другие i18n-файлы.

## Acceptance criteria

- [ ] PlayerBar использует MotionPress + MorphIcon + BeatPulse + SharedCover. Liquid Glass заметен.
- [ ] Свайп-вверх с PlayerBar открывает /now-playing с shared-layout transition обложки.
- [ ] На NowPlayingView работают табы Now/Lyrics/Queue.
- [ ] Drag-down на NowPlayingView закрывает экран.
- [ ] QueueSheet — swipe-actions работают на каждом ряду.
- [ ] Equalizer — bottom-sheet с drag-to-close.
- [ ] Like-burst заметный, монохромный.
- [ ] reduced-motion отключает spring, Ken Burns, beat pulse, swipe rubber-band.
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. Делай работу разделом за разделом, по одному коммиту на каждый раздел.
3. Перед каждым коммитом: `git pull --rebase` + `npx tsc --noEmit` + (по возможности) `npm run build`.
4. Conventional Commits с scope `redesign-a`. Примеры:
   - `feat(redesign-a): rebuild PlayerBar with liquid glass and morph icons`
   - `feat(redesign-a): add full-screen NowPlayingView with tabs`
   - `feat(redesign-a): restyle FullscreenLyrics for now-playing layout`
   - `feat(redesign-a): swipe-actions in QueueSheet`
   - `feat(redesign-a): refresh Equalizer as bottom-sheet`
5. Push в `redesign/ios-2026` после каждого коммита.

Когда все acceptance criteria выполнены и пушнуто — сообщи мне отдельным сообщением, что Stage-A готов.
