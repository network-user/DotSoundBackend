# STAGE-C — Home, Discovery, Radio, NotFound

> Параллельный этап. Стартует после Stage-0.

## Цель

Сделать главный экран максимально «магнетическим» — большие герои, snap-карусели
с parallax, морф-иконки в quick-grid, ambient-цвет на герое-выборе дня.
Радио — отдельная атмосферная сцена. Жанровые миксы и подборки —
ритмичные карусели в Apple Music-стиле.

## Owned files

```
frontend/src/views/HomeView.tsx
frontend/src/views/DailyMixView.tsx
frontend/src/views/WeeklyMixView.tsx
frontend/src/views/UserChoiceView.tsx
frontend/src/views/WeeklyTopView.tsx
frontend/src/views/GenreMixView.tsx
frontend/src/views/RadioView.tsx
frontend/src/views/NotFoundView.tsx
frontend/src/styles/redesign-home.css
```

## No-touch

Стандартный список (см. SHARED-CONTRACTS § 6).
**Особо:** `lib/api.ts` не править. Если поля нет — `TODO(redesign-2026)` и
заглушка.

## Что сделать

### 1. HomeView v3

- Hero-карточка дня (top): большая обложка, ambient-фон через
  `<AmbientStage>`, KenBurns на cover. Под обложкой — заголовок large-title +
  primary CTA «Слушать» (`MotionPress variant="primary"`).
- Quick-grid на 4–6 ярлыков (Liked, Daily, Weekly, Radio, User-choice,
  Weekly-top): карточки с `<MorphIcon>` + glass-medium. На active filled.
- Секционные карусели: `<HorizontalSnap parallax pageDots>` с большими
  обложками. Каждый item — `<MotionPress>` (открывает плеер /
  переход на детальный mix).
- Followed-artists strip: горизонтальные круги-аватарки, нажатие — карточка
  артиста.
- Genre mixes carousel — то же.

### 2. Daily/Weekly/UserChoice/WeeklyTop/GenreMix views

- Header: heroы с ambient + KenBurns + большая обложка.
- TrackList снизу — пусть TrackList пока не редизайнится в этом этапе (он
  у Stage-E). Просто оборачиваем в `<m.div variants={VARIANTS_FADE_UP}>`.
- На каждом view добавить `Play all` primary button + `Shuffle` secondary.
  При нажатии запускается обычный playback queue.

### 3. RadioView

- Hero-сцена: вращающийся диск (KenBurns на абстрактной композиции / на
  обложке текущего трека). BeatPulse в центре.
- Quick-стартеры — 6 «настроений» (chill, focus, gym, cinematic, retro,
  acoustic) в виде карточек `glass--liquid`. Иконки морф.
- Active radio session: большая полноэкранная сцена с AmbientStage от текущей
  обложки.

### 4. NotFoundView

- Центрированная иллюстрация (text-only, large-title), `MotionPress` ←
  «На главную». Лаконично.

### 5. Стили

`redesign-home.css`. Префикс классов: `.rh-...`. Никаких глобальных утилитарных
классов — все scoped.

## Hint-снипет

```tsx
// HomeView.tsx
import { m, VARIANTS_FADE_UP } from '@/lib/motion'
import { HorizontalSnap } from '@/components/ui/HorizontalSnap'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'

export function HomeView({ onOpenArtist }: Props) {
  ...
  return (
    <m.div className="view rh-home" variants={VARIANTS_FADE_UP}
      initial="hidden" animate="visible"
    >
      <header className="rh-home__greeting">
        <h1 className="rh-home__title">{greeting}</h1>
      </header>

      <section className="rh-home__hero">
        <AmbientStage coverUrl={hero.cover_url} className="rh-home__hero-bg">
          <KenBurnsCover src={hero.cover_url} alt={hero.title} />
          <div className="rh-home__hero-meta">
            <h2>{hero.title}</h2>
            <MotionPress variant="primary" haptic="medium" onClick={playHero}>
              Слушать
            </MotionPress>
          </div>
        </AmbientStage>
      </section>

      <section className="rh-home__grid">
        {QUICK.map(it => (
          <MotionPress key={it.path} className="rh-home__quick"
            variant="ghost" haptic="selection" onClick={() => navigate(it.path)}>
            <MorphIcon name={it.icon} filled />
            <span>{t(it.labelKey)}</span>
          </MotionPress>
        ))}
      </section>

      <section className="rh-home__row">
        <h3 className="rh-home__row-title">Дневной микс</h3>
        <HorizontalSnap items={dailyTracks} renderItem={(tr) => <BigCoverCard track={tr} />} parallax />
      </section>
      ...
    </m.div>
  )
}
```

## Acceptance criteria

- [ ] Home hero — большой, с ambient + KenBurns.
- [ ] Quick-grid на морф-иконках.
- [ ] Карусели — snap + parallax + dots.
- [ ] Daily/Weekly/User/WeeklyTop/Genre — общий «герой» на старте экрана.
- [ ] Radio — атмосферная сцена с beat-pulse.
- [ ] NotFound — лаконично с MotionPress.
- [ ] reduced-motion корректен (KenBurns статичен, parallax отключен).
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-c): rebuild HomeView with hero ambient and snap carousels
feat(redesign-c): polish daily/weekly/user-choice/weekly-top/genre mix views
feat(redesign-c): atmospheric RadioView with beat pulse hero
chore(redesign-c): refresh NotFoundView with motion primitives
```
