# STAGE-A — Player Stack

> Параллельный этап. Стартует ТОЛЬКО после успешного завершения Stage-0.
> Перед коммитом — `git pull --rebase origin redesign/ios-2026`.

## Цель

Полностью переделать стек плеера в iOS-стилистике: PlayerBar (мини), Now Playing
(полный экран), очередь, эквалайзер, Fullscreen Lyrics. Это «лицо»
взаимодействия с музыкой — должно ощущаться на уровне Apple Music.

## Owned files (мой эксклюзив)

```
frontend/src/components/PlayerBar/PlayerBar.tsx
frontend/src/components/FullscreenLyrics/FullscreenLyrics.tsx
frontend/src/components/FullscreenLyrics/*               (если есть suborg)
frontend/src/components/QueueSheet/QueueSheet.tsx
frontend/src/components/Equalizer/Equalizer.tsx
frontend/src/views/NowPlayingView.tsx                    (переписать stub)
frontend/src/styles/redesign-player.css
```

## No-touch (см. SHARED-CONTRACTS § 6 + § 5)

- `frontend/src/lib/api.ts`, `types/api.ts`, `store/**`, `App.tsx`, `main.tsx`,
  `Icon.tsx`, `tokens.css`, `global.css`, `components.css`, `animations.css`,
  `redesign-shared.css`.
- Любые файлы вне списка Owned.

## Что сделать

### 1. PlayerBar v3

Внешний вид: тонкая полоса внизу, **Liquid Glass** (`.glass--liquid`),
ambient-glow от текущей обложки (используя `extractCoverPalette` через
`AmbientStage` или ручной gradient), beat-pulse на иконке Play, scrub-полоса
с rubber-band overscroll.

- Заменить старые `<button>` на `<MotionPress>` для всех контролов.
- Заменить статичный `<Icon name="play" />` на
  `<MorphIcon name="play" filled={isPlaying} />`. Пара play/pause морфит при
  переключении состояния.
- Like-кнопку — `<MorphIcon name="heart" filled={liked} />` + сохранить
  существующий burst-ring эффект (можно через framer-motion вместо CSS).
- Обернуть всю полосу в `<BeatPulse bpm={derivedBpm} active={isPlaying}>` либо
  применить точечно к иконке Play.
- На мини-обложке плеера использовать `<SharedCover trackId={trackId} />` —
  так при swipe-up в Now Playing она «вырастет» в большую через layout.
- Прогресс-бар: тот же scrubber, но при touch-down — расширяется (`scaleY` 1.5),
  на release — обратно. Через `m.div` + `whileTap`.
- Overflow-меню — `<LongPressMenu>` (или просто `MotionPress` + старое меню,
  но c motion-вход/выход).

### 2. Now Playing — новый full-screen

`/now-playing` (роут уже зарегистрирован Stage-0). По свайпу-вверх с PlayerBar:

- Открывается с layout-shared transition: обложка из мини-плеера вырастает в
  большую (`<SharedCover trackId={...} />`).
- Фон — `<AmbientStage coverUrl={...}>` + лёгкая `<KenBurnsCover>` поверх.
- Контролы по центру, крупные. `<MorphIcon>` для play/pause/heart.
- Под обложкой — три таба: **Now Playing**, **Lyrics**, **Queue** (стиль
  segmented control, mono).
  - Now Playing: метаданные, контролы, slider scrubber, доп. действия.
  - Lyrics: рендерим `<FullscreenLyrics>` (его же редизайним) inline.
  - Queue: рендерим `<QueueSheet>` (или его контент) inline; обычный
    оверлей-вариант QueueSheet остаётся, но уже как «выскочить отдельно» из
    PlayerBar dropdown.
- Сверху — `<MotionPress variant="icon">` со стрелкой вниз (chevron-down)
  закрывает экран.
- Жест swipe-down закрывает (drag-y, threshold ~120 px, snap-back spring).
- Кнопка «лайк» — c spring + burst.
- Кнопка «share» — открывает существующий share-flow (используем как есть).

### 3. FullscreenLyrics — мягкий ребрендинг

- Глобально оставить как есть (логику не ломаем).
- Передвинуть контролы в верхнюю часть (Apple Music style: маленькая обложка
  слева, контролы справа); большая часть экрана — текст с line-by-line follow.
- При активной строке: `m.span` с `layout` + spring.
- Beat pulse на маленькой обложке.

### 4. QueueSheet — рестайл

- Тот же оверлей, но с `<m.div>` slide-up через `VARIANTS_SHEET_SLIDE_UP`.
- Каждый row очереди обернуть в `<SwipeRow>` с right-action: «Удалить из
  очереди» (destructive). Дефолтное взаимодействие — клик — играет трек, как
  раньше.
- На текущем играющем — beat-pulse-индикатор (заменить queue-eq бары).

### 5. Equalizer

- Полностью переделать в bottom-sheet `m.div`. Drag-down закрывает.
- Слайдеры — `<input type="range">` со spring-pop при изменении (масштабирование
  thumb).
- Включить / выключить — toggle-pill, `<MotionPress>`.

### 6. Стили

Все классы — в `redesign-player.css`. Префикс классов: `.rp-player-...`,
`.rp-now-...`, `.rp-queue-...`, `.rp-eq-...`, чтобы не пересечься с другими.

## Hint-снипеты

```tsx
// PlayerBar.tsx (фрагмент)
import { m, useReducedMotion } from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { SharedCover } from '@/components/ui/SharedCover'
import { AmbientStage } from '@/components/ui/AmbientStage'

export function PlayerBar() {
  const reduceMotion = useReducedMotion()
  ...
  return (
    <m.aside id="player-bar" className="rp-player glass--liquid"
      whileTap={reduceMotion ? undefined : { y: -1 }}
    >
      <AmbientStage coverUrl={track?.cover_url} className="rp-player__ambient">
        <div className="rp-player__row">
          <SharedCover trackId={track.id} src={track.cover_url} className="rp-player__cover" />
          <div className="rp-player__meta"> ... </div>
          <BeatPulse bpm={120} active={isPlaying}>
            <MotionPress variant="icon" haptic="medium" onClick={togglePlay}>
              <MorphIcon name="play" filled={isPlaying} size={24} />
            </MotionPress>
          </BeatPulse>
        </div>
      </AmbientStage>
    </m.aside>
  )
}
```

```tsx
// NowPlayingView.tsx (структура)
return (
  <m.section className="rp-now"
    initial="hidden" animate="visible" exit="exit"
    variants={VARIANTS_SHEET_SLIDE_UP}
    drag="y" dragConstraints={{ top: 0, bottom: 0 }}
    onDragEnd={(_, info) => info.offset.y > 120 && navigate(-1)}
  >
    <AmbientStage coverUrl={track.cover_url} className="rp-now__bg" />
    <div className="rp-now__head"> ...close, more... </div>
    <KenBurnsCover>
      <SharedCover trackId={track.id} src={track.cover_url} />
    </KenBurnsCover>
    <div className="rp-now__meta"> ...title, artist, badges... </div>
    <div className="rp-now__scrubber"> ...slider... </div>
    <div className="rp-now__ctl"> ...prev/play/next + like/share... </div>
    <Tabs>
      <Tab id="now-playing"> ...current... </Tab>
      <Tab id="lyrics"> <FullscreenLyrics inline /> </Tab>
      <Tab id="queue"> <QueueSheet inline /> </Tab>
    </Tabs>
  </m.section>
)
```

## Acceptance criteria

- [ ] PlayerBar использует `MotionPress` + `MorphIcon` + `BeatPulse` +
      `SharedCover`. Liquid Glass — заметен.
- [ ] Свайп-вверх с PlayerBar открывает `/now-playing`. Обложка плавно
      «перетекает» (shared layout).
- [ ] На Now Playing работают табы Now/Lyrics/Queue.
- [ ] Drag-down на Now Playing закрывает экран.
- [ ] QueueSheet — swipe-actions работают на каждом ряду.
- [ ] Equalizer — bottom-sheet с drag-to-close.
- [ ] Like-burst заметный, но не цветной (монохром).
- [ ] `prefers-reduced-motion: reduce` отключает spring и Ken Burns.
- [ ] `npm run build` зелёный.

## Коммиты (пример последовательности)

```
feat(redesign-a): rebuild PlayerBar with liquid glass and morph icons
feat(redesign-a): add full-screen NowPlayingView with tabs
feat(redesign-a): restyle FullscreenLyrics for now-playing layout
feat(redesign-a): swipe-actions in QueueSheet
feat(redesign-a): refresh Equalizer as bottom-sheet
```
