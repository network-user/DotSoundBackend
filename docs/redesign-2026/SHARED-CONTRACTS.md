# SHARED CONTRACTS — единый справочник для всех потоков редизайна

Этот файл — единственный источник правды для:

- API общих primitives, которые ставит Stage-0;
- дизайн-токенов и spring-presets;
- правил, обязательных ВСЕМ потокам (A–I, Z);
- списка файлов, которые **никто не трогает** в параллельной фазе.

Если что-то здесь не описано — значит, либо это лежит в области конкретного
этапа, либо требует поднять вопрос владельцу. Не выдумывай.

---

## 0. Обязательные правила для всех потоков

1. **Не трогать**: `app/`, `alembic/`, `dotsound_private_core/`, `bot/`, любой
   compute-worker. Это редизайн **только** фронтенда.
2. **Не менять backend API клиент** (`frontend/src/lib/api.ts`,
   `frontend/src/types/api.ts`). Если для UI нужны новые поля — оставляй
   `TODO(redesign-2026):` коммент и UI-заглушку, а не правь клиент.
3. **Не править `frontend/src/components/Icon/Icon.tsx`** в фазах A–I.
   Все нужные иконки добавляет Stage-0 одним проходом. Если в твоём этапе
   физически не хватает иконки — в STAGE-Z собирается список и добавляется
   разом.
4. **Не менять `frontend/src/main.tsx` и общие провайдеры** (`PlayerProvider`,
   `LikesProvider`, `ToastProvider`, `SoundProvider`, `AdminProvider`)
   в фазах A–I. Stage-0 уже подмонтирует туда DynamicIslandHost и нужные CSS.
5. **Не менять `frontend/src/App.tsx` структуру маршрутов** в фазах A–I.
   Stage-0 заранее регистрирует пустые роуты для `/now-playing` и `/recap`
   как lazy-импорты. Реализация компонентов происходит в этапе-владельце.
6. **Монохром-правило не отменено.** Никаких `systemBlue/Pink/...`. Только
   `--bg/--surface/--text/--text-secondary/--accent/--border/--glass-*`.
   Полупрозрачные слои стекла допустимы, но без оттенков.
7. **Без эмодзи в UI.** Только `<Icon>` или `<MorphIcon>`.
8. **Reduced-motion** обязателен. Любая loop-анимация и любой spring должны
   уважать `prefers-reduced-motion: reduce`.
9. **i18n**: ключи добавлять только в `frontend/src/locales/i18n_extra2_ru.json`
   и `i18n_extra2_en.json`. Namespace = id этапа: `redesign.player.*`,
   `redesign.home.*`, и т. д. Не править `ru.json` / `en.json` /
   `i18n_extra_*.json` в параллельной фазе.
10. **CSS**: каждый этап пишет в свой файл `frontend/src/styles/redesign-<id>.css`.
    Stage-0 создаёт пустые файлы и импортирует их в `main.tsx`. В фазах
    A–I — не трогать `tokens.css`, `global.css`, `components.css`,
    `animations.css`. Чистка legacy — задача STAGE-Z.
11. **Bundle hygiene**: запрещено добавлять новые npm-зависимости без
    согласования. Для редизайна разрешён только `framer-motion` (его ставит
    Stage-0).
12. **Public/Private boundary**: фронт — публичная зона, никаких бизнес-правил
    в коде. PrivateCore-внутренности (model names, providers, scoring) даже
    в комментах фронта не упоминать.
13. **Перед коммитом**: `git pull --rebase origin redesign/ios-2026` и
    `npm run build` локально (или хотя бы `tsc --noEmit`).
14. **Conventional Commits**, scope = id этапа, на английском, одна строка в
    summary, тело — опционально.

---

## 1. Палитра и токены

Все токены живут в `frontend/src/styles/tokens.css`. Stage-0 расширяет файл,
дальше **никто его не трогает**.

### Цветовые токены (dark only, монохром)

```css
--bg                 base background
--surface            elevated surface (card)
--surface-2          deeper card / inset
--text               primary text
--text-secondary     muted text (hints, meta)
--text-muted         very muted (timestamps)
--accent             monochrome accent (white-ish)
--accent-hover       slightly dim accent for hover
--border             subtle dividers
--glass-tint-1/2/3   glass background tints
--glass-tint-liquid  visionOS-style brighter liquid layer
--glass-edge         hairline border on glass
--glass-edge-bright  brighter edge for important strips
--glass-blur-soft/medium/strong   backdrop-filter blur values
--glass-saturate                   backdrop saturation
--glass-backdrop-fixed             композит для fixed strips
--glass-backdrop-fixed-player      специально для PlayerBar
--glass-top-shine                  Frutiger Aero gradient gloss
--glass-highlight                  альтернативный highlight
--glass-noise-opacity              шум на стекле (subtle)
```

Семантические state-токены (`--state-ok/warn/error/unknown`) — **только** для
admin-панели в `<StatusPill>` и `<KpiCard>`. В публичном UI не использовать.

### Spacing / Radii / Type / Motion / Z

См. `tokens.css`. Stage-0 добавляет:

- `--fs-lt: 34px` (large title) и `--fs-tt: 28px` (title 1) для Apple-стиля
  заголовков, плюс выровненные `letter-spacing`.
- `--font-stack-system` — system-ui SF/Roboto cascade.
- CSS-переменные spring-параметров (для CSS-only анимаций):
  `--spring-stiff-x`, `--spring-soft-x`, `--spring-bouncy-x`. Они не используются
  напрямую — это семантические алиасы для существующих cubic-bezier easing.

---

## 2. Spring presets — `frontend/src/lib/motion.ts`

Stage-0 создаёт этот файл. Все потоки импортируют из него и **не дублируют**
свои собственные спринги.

```ts
export const SPRING_GENTLE   // мягкий, для входов/выходов
export const SPRING_SNAPPY   // быстрый, для микро-нажатий
export const SPRING_BOUNCY   // эмфаза, для лайков/успехов
export const SPRING_LAYOUT   // для motion layout transitions
export const TWEEN_FAST      // tween fallback под reduced-motion
export const TWEEN_SLOW      // длинные fade
export const VARIANTS_FADE_UP        // { hidden, visible }
export const VARIANTS_SCALE_IN       // { hidden, visible }
export const VARIANTS_PAGE_SLIDE     // { hidden, visible, exit }
export const VARIANTS_SHEET_SLIDE_UP // { hidden, visible, exit }

export function shouldReduceMotion(): boolean
export function withReduce<T>(motion: T, reducedFallback: T): T
```

Все потоки оборачивают использование Framer Motion в `<LazyMotion features={domAnimation}>`. Stage-0 ставит этот wrapper в `App.tsx`. В фазах A–I — просто `import { m } from 'framer-motion'` (lowercase `m`, не `motion`), чтобы не тянуть полный bundle.

---

## 3. Primitives — что ставит Stage-0

Все живут в `frontend/src/components/ui/`. Любая фаза A–I использует их по
импорту, **не реализует свои аналоги**.

### `<MotionPress>` — spring-кнопка

Замена `<Press>` для новых компонентов. Старый `Press` остаётся для legacy
участков; в STAGE-Z может быть удалён, если все мигрировали.

```tsx
<MotionPress
  variant="primary" | "ghost" | "icon" | "subtle"
  haptic="light" | "medium" | "heavy" | "selection" | null
  onClick={...}
  disabled={...}
  ariaLabel="..."
>
  ...
</MotionPress>
```

- Использует `m.button` с `whileTap={{ scale: 0.96 }}` (spring snappy).
- На tap вызывает `haptic(...)` из `lib/telegram`.
- Поддерживает focus ring через `:focus-visible`.
- Под `prefers-reduced-motion` отключает spring и используется простой press-state.

### `<MorphIcon>` — анимированная иконка

Морфит между outline и filled через Framer Motion `<motion.path>` интерполяцию
`d` (через `flubber` через path-strings заранее заданных пар).

Stage-0 готовит **пары** outline/filled для:
`heart`, `play`, `pause`, `star`, `bookmark`, `home`, `search`, `library`,
`chats`, `profile`, `radio`, `users-following`, `flame`.

```tsx
<MorphIcon name="heart" filled={liked} size={20} />
<MorphIcon name="play"  filled={playing} size={20} />
```

- При `filled` меняется не только path, но и `fill` через `m.path` от
  `transparent` к `currentColor` за 240 мс.
- Loop отсутствует, морф — однократный per state-change.

### `<SwipeRow>` — свайп-actions

Обёртка вокруг строки списка. Поддерживает `leftAction` и `rightAction`,
rubber-band, threshold, snap-back, hint при достижении threshold + haptic.

```tsx
<SwipeRow
  leftAction={{ icon: 'heart', label: 'Лайк', onTrigger: ... }}
  rightAction={{ icon: 'queue', label: 'В очередь', onTrigger: ..., destructive: false }}
>
  <TrackRow ... />
</SwipeRow>
```

Внутри — `m.div` с `drag="x"`, `dragConstraints`, `dragElastic`, threshold ~80 px.

### `<LongPressMenu>` — iOS context-menu

Обёртка вокруг любого триггера. На long-press (~450 мс) показывает overlay:
backdrop blur, scale-down превью триггера, набор пунктов в стеклянной карточке.

```tsx
<LongPressMenu
  items={[
    { id: 'like',   label: 'В любимые', icon: 'heart',   onPick: ... },
    { id: 'queue',  label: 'В очередь', icon: 'queue',   onPick: ... },
    { id: 'share',  label: 'Поделиться', icon: 'share',  onPick: ... },
    { id: 'remove', label: 'Удалить',    icon: 'trash',  onPick: ..., destructive: true },
  ]}
>
  <TrackCard ... />
</LongPressMenu>
```

Reduced-motion: показывает обычный popover без масштабирования.

### `<DynamicIsland>` + `<DynamicIslandHost>`

Pill вверху экрана для:
- toast-уведомлений,
- мини-«сейчас играет» при прокрутке вниз,
- прогресса upload/import,
- ошибок WebSocket reconnect.

Host один на приложение, монтируется в `App.tsx` Stage-0. API:

```ts
import { showIsland, dismissIsland } from '@/lib/island'

const id = showIsland({
  kind: 'now-playing' | 'toast' | 'progress' | 'error',
  title: '...',
  hint?: '...',
  iconName?: 'music' | 'flame' | 'check' | ...,
  progress?: 0..1,
  onClick?: () => void,
  durationMs?: number,
})
dismissIsland(id)
```

Под капотом — `framer-motion` `AnimatePresence` + `layout` (для shape-shift между
pill и full-bar).

### `<AmbientStage>` — фон из палитры обложки

```tsx
<AmbientStage coverUrl={track.cover_url}>
  ...children...
</AmbientStage>
```

- Извлекает 2–3 доминантных тона через `lib/coverPalette.ts` (canvas
  downsample 32×32, k-means light).
- Рендерит размытый mesh-gradient на фоне (3 radial-gradient слоя).
- Cross-fade при смене обложки за 600 мс.
- На reduced-motion статика.
- Уважает монохром: тоны проходят через `desaturate` фильтр до ~30% (только
  валёр и тон, без насыщенного цвета).

### `<KenBurnsCover>` — медленный pan/zoom обложки

```tsx
<KenBurnsCover src={url} alt="..." duration={18} />
```

Анимация 12–24 с, бесконечный цикл (если `prefers-reduced-motion` не reduce).

### `<BeatPulse>` — пульс в такт

```tsx
<BeatPulse bpm={120} active={isPlaying}>
  <Icon name="play" />
</BeatPulse>
```

- BPM по умолчанию 120 если не передан.
- Использует `currentTime` из `usePlayerState()` через requestAnimationFrame,
  чтобы фаза не плыла при паузе.
- При `prefers-reduced-motion` — без пульсации.

### `<HorizontalSnap>` — снэп-карусель

```tsx
<HorizontalSnap items={cards} renderItem={(c) => <Card ... />}
   pageDots showArrows="md+"
   parallax 
/>
```

- CSS scroll-snap, JS-страничный индекс, dots снизу, arrow-controls на ≥ md.
- `parallax` — сдвиг внутри карточки на основе scrollLeft.

### `<SharedCover>` — shared-element обертка

Обёртка для `m.img` / `m.div` с `layoutId`. Stage-0 ставит, потоки A
(Now Playing) и E (TrackCardSheet) совместно используют через одинаковый
`layoutId={`cover-${trackId}`}`.

```tsx
<SharedCover trackId={track.id} src={track.cover_url} />
```

---

## 4. Утилиты

### `lib/motion.ts` (Stage-0)

См. раздел 2.

### `lib/coverPalette.ts` (Stage-0)

```ts
export interface CoverPalette {
  tones: [string, string, string]   // 3 тона hex для AmbientStage
  text: 'light' | 'dark'             // подсказка для overlay-текста
}
export async function extractCoverPalette(url: string): Promise<CoverPalette | null>
```

Кэшируется в Map по URL. Crossorigin handled. Network failure → null (callers
fallback на дефолтный фон).

### `lib/island.ts` (Stage-0)

Императивный API хоста:

```ts
showIsland(input): string         // returns id
dismissIsland(id?: string): void  // если без id — закрывает все
```

### `lib/haptics.ts` (опционально, Stage-0)

Обёртка над существующими `haptic`, `hapticNotification`, `hapticSelection` —
семантический dispatcher с throttle. Существующие функции в `lib/telegram.ts`
не удаляем.

---

## 5. Файлы — карта владения по этапам

> Каждая ячейка — *эксклюзивный* владелец файлов в фазе A–I. Stage-0 трогает
> всё перечисленное в "общее" + создаёт пустые scaffold-файлы для остальных.

### Общее (Stage-0 only)

```
frontend/package.json                      # +framer-motion
frontend/src/main.tsx                      # импорты CSS + LazyMotion-обёртка
frontend/src/App.tsx                       # маршруты-stub, DynamicIslandHost
frontend/src/styles/tokens.css             # расширение
frontend/src/styles/global.css             # ТОЛЬКО body{font-family} строкой
frontend/src/styles/components.css         # не трогаем (legacy)
frontend/src/styles/animations.css         # не трогаем (legacy)
frontend/src/styles/redesign-shared.css    # NEW (общие классы glass/island)
frontend/src/styles/redesign-<id>.css      # NEW пустышки на каждый этап
frontend/src/components/ui/MotionPress.tsx
frontend/src/components/ui/MorphIcon.tsx
frontend/src/components/ui/SwipeRow.tsx
frontend/src/components/ui/LongPressMenu.tsx
frontend/src/components/ui/DynamicIsland.tsx
frontend/src/components/ui/AmbientStage.tsx
frontend/src/components/ui/KenBurnsCover.tsx
frontend/src/components/ui/BeatPulse.tsx
frontend/src/components/ui/HorizontalSnap.tsx
frontend/src/components/ui/SharedCover.tsx
frontend/src/lib/motion.ts                 # NEW
frontend/src/lib/island.ts                 # NEW
frontend/src/lib/coverPalette.ts           # NEW
frontend/src/lib/haptics.ts                # NEW (optional)
frontend/src/components/Icon/Icon.tsx      # +все нужные новые иконки
frontend/src/locales/i18n_extra2_*.json    # каркас redesign.* namespace
docs/design-system.md                      # +раздел "Redesign 2026 primitives"
```

### Stage-A — Player Stack

```
frontend/src/components/PlayerBar/PlayerBar.tsx
frontend/src/components/FullscreenLyrics/FullscreenLyrics.tsx
frontend/src/components/FullscreenLyrics/*
frontend/src/components/QueueSheet/QueueSheet.tsx
frontend/src/components/Equalizer/Equalizer.tsx
frontend/src/views/NowPlayingView.tsx                # NEW
frontend/src/styles/redesign-player.css              # NEW
```

### Stage-B — Nav, Auth, Onboarding, Banned

```
frontend/src/components/BottomNav/BottomNav.tsx
frontend/src/components/Onboarding/**
frontend/src/components/Auth/**
frontend/src/components/BannedScreen/**
frontend/src/components/PwaInstall/InstallPrompt.tsx
frontend/src/components/ui/OfflineBanner.tsx
frontend/src/styles/redesign-nav.css                 # NEW
```

### Stage-C — Home, Discovery, Radio

```
frontend/src/views/HomeView.tsx
frontend/src/views/DailyMixView.tsx
frontend/src/views/WeeklyMixView.tsx
frontend/src/views/UserChoiceView.tsx
frontend/src/views/WeeklyTopView.tsx
frontend/src/views/GenreMixView.tsx
frontend/src/views/RadioView.tsx
frontend/src/views/NotFoundView.tsx
frontend/src/styles/redesign-home.css                # NEW
```

### Stage-D — Library, Search, Profile, Settings

```
frontend/src/views/SearchView.tsx
frontend/src/views/LibraryView.tsx
frontend/src/views/LikedView.tsx
frontend/src/views/PlaylistsView.tsx
frontend/src/views/ProfileView.tsx
frontend/src/components/Settings/**
frontend/src/components/Profile/**
frontend/src/styles/redesign-library.css             # NEW
```

### Stage-E — TrackCard, TrackCardSheet, Comments, Chat, Legal

```
frontend/src/components/TrackCard/TrackCard.tsx
frontend/src/components/TrackList/TrackList.tsx
frontend/src/components/TrackCardSheet/**
frontend/src/components/Comments/**
frontend/src/components/Chat/**
frontend/src/views/ChatView.tsx
frontend/src/views/ChatsView.tsx
frontend/src/views/LegalView.tsx
frontend/src/views/LegalDocView.tsx
frontend/src/components/ComplaintModal/**
frontend/src/styles/redesign-tracks.css              # NEW
```

### Stage-F — Artist, Author

```
frontend/src/components/ArtistView/**
frontend/src/components/AuthorView/**
frontend/src/views/ArtistStatsView.tsx
frontend/src/styles/redesign-artist.css              # NEW
```

### Stage-G — Admin

```
frontend/src/admin/**                                # все файлы админки
frontend/src/admin/styles/admin.css
```

Админ-чанк собирается отдельным bundle. Внутри можно вольно использовать новые
primitives из `components/ui/`. State-токены (`--state-ok/warn/error/unknown`)
остаются ТОЛЬКО внутри admin (правило design-system).

### Stage-H — Wrapped/Recap

```
frontend/src/views/RecapView.tsx                     # NEW
frontend/src/components/Recap/**                     # NEW
frontend/src/styles/redesign-recap.css               # NEW
```

API: использует существующие `api.getMyStats`, `api.getMyTopTracks` и т. п.
из `lib/api.ts`. Если данных не хватает — заглушка с TODO без правки api.ts.

### Stage-I — Upload, Import

```
frontend/src/views/UploadView.tsx
frontend/src/components/Upload/**
frontend/src/components/Import/**
frontend/src/styles/redesign-upload.css              # NEW
```

### Stage-Z — Finalize

Все файлы, по согласованию с владельцем. В частности:
- `frontend/src/styles/global.css` (удаление мёртвого CSS, миграция оставшегося)
- `frontend/src/styles/components.css`
- `frontend/src/styles/animations.css`
- `docs/design-system.md`
- `TODO.md`

---

## 6. Список «no-touch» (для всех A–I)

```
frontend/src/lib/api.ts
frontend/src/types/api.ts
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/store/**
frontend/src/hooks/**           (кроме случаев, когда фаза прямо владеет хуком — тогда отдельная договорённость)
frontend/src/locales/ru.json
frontend/src/locales/en.json
frontend/src/locales/i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/styles/tokens.css
frontend/src/styles/global.css
frontend/src/styles/components.css
frontend/src/styles/animations.css
frontend/src/styles/redesign-shared.css
frontend/src/components/ui/MotionPress.tsx
frontend/src/components/ui/MorphIcon.tsx
frontend/src/components/ui/SwipeRow.tsx
frontend/src/components/ui/LongPressMenu.tsx
frontend/src/components/ui/DynamicIsland.tsx
frontend/src/components/ui/AmbientStage.tsx
frontend/src/components/ui/KenBurnsCover.tsx
frontend/src/components/ui/BeatPulse.tsx
frontend/src/components/ui/HorizontalSnap.tsx
frontend/src/components/ui/SharedCover.tsx
frontend/src/lib/motion.ts
frontend/src/lib/island.ts
frontend/src/lib/coverPalette.ts
docs/redesign-2026/**
backend/, app/, alembic/, dotsound_private_core/, bot/, ComputeWorker/  — всё
```

Если что-то из этого нужно поменять — поднимай вопрос владельцу. Не правь сам.

---

## 7. Чек-лист «готов к коммиту» для любого этапа

- [ ] `git pull --rebase origin redesign/ios-2026` без конфликтов.
- [ ] Все мои изменения только в файлах, перечисленных в моей секции
      (раздел 5).
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` (если ставил deps) — зелёный.
- [ ] Никаких новых npm-зависимостей кроме `framer-motion` (которое уже
      зафиксировано Stage-0).
- [ ] `prefers-reduced-motion: reduce` на Devtools проверен на хотя бы одном
      моём экране — все loop-анимации замёрзли.
- [ ] Никаких эмодзи в UI и коммитах.
- [ ] Никакого упоминания PrivateCore-технологий и провайдеров.
- [ ] i18n-ключи добавлены в `i18n_extra2_ru.json` и `i18n_extra2_en.json`
      под мой namespace.
- [ ] Conventional Commit с правильным scope.
