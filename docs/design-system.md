# DotSound Design System

This document describes the design tokens and the shared UI
primitives that ship with the Mini App. They live in
`frontend/src/styles/tokens.css`,
`frontend/src/styles/components.css` and
`frontend/src/components/ui/`.

The system targets Telegram WebApp first and the desktop browser
second. It deliberately stays monochrome; the only colour token
that ever changes is the optional accent.

## Foundations

### 8pt grid

Spacing is exposed via `--space-1 .. --space-10`, mapping to
`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 56 / 72` pixels. Use the
tokens directly instead of literal pixel values.

### Type scale

`--fs-12`, `--fs-13`, `--fs-14`, `--fs-15`, `--fs-16`, `--fs-18`,
`--fs-22`, `--fs-28`, `--fs-36`, `--fs-48`. Line-heights:
`--lh-tight (1.2)`, `--lh-normal (1.5)`, `--lh-loose (1.7)`.

### Radius

`--r-sm (6px)`, `--r-md (10px)`, `--r-lg (16px)`, `--r-xl (24px)`,
`--r-pill (999px)`.

### Motion

| Token            | Value                                 |
| ---------------- | ------------------------------------- |
| `--dur-fast`     | 120ms                                 |
| `--dur-med`      | 220ms                                 |
| `--dur-slow`     | 360ms                                 |
| `--ease-standard`| `cubic-bezier(.2, 0, 0, 1)`           |
| `--ease-emph`    | `cubic-bezier(.3, 0, 0, 1.2)`         |

All `--dur-*` tokens collapse to `0ms` automatically when the
user has `prefers-reduced-motion: reduce`.

### Tap targets and safe areas

- Minimum tap-target: `--tap = 44px` (Apple HIG / WCAG 2.1).
- Safe area helpers: `--safe-top`, `--safe-right`, `--safe-bottom`,
  `--safe-left`. The fixed bottom UI (`#nav`, `#player-bar`,
  `#main`) already accounts for `env(safe-area-inset-bottom)`.
- **Player bar:** mini cover (~48px), slightly larger title/artist
  type (`global.css` `.pb-title` / `.pb-artist`), transport controls
  **prev · play · next · like · overflow** on narrow layouts; from
  **561px** width up, a **volume** control (popover) appears before the
  like button. Coarse-pointer landscape phones still hide the bar
  volume (`global.css`). Otherwise volume is also available from the
  track sheet / expanded player.

### Z-index scale

`#player-bar` and `#nav` in `global.css` use fixed **165–166** so
tokenized overlays (`--z-sheet`, `--z-modal`) must sit **above**
those layers or dialogs (e.g. admin step-up `Sheet`) end up under
the player.

```
--z-nav:    80
--z-player: 90
--z-sheet:  180
--z-modal:  185
--z-toast:  200
```

## Colour and theming

The palette is strictly **monochrome** (black + white + neutral
greys) and is **NOT** overridden by Telegram theme parameters.
The colour tokens defined in `frontend/src/styles/global.css`
(`--bg`, `--surface`, `--text`, `--text-secondary`, `--accent`,
`--border`, glass tokens `--glass-bg / --glass-blur /
--glass-border`) are the single source of truth in every theme
(Telegram Light / Dark / Sea / Custom).

`installTelegramThemeBridge()` in `frontend/src/lib/telegram.ts`
is intentionally a no-op kept only for backwards compatibility
of imports. If at some point a thin opt-in adaptation to the
Telegram theme is needed (e.g. matching only the system bar
colour, not the UI palette), it should be exposed through an
explicit user setting — never enabled automatically.

Surfaces that need an iOS-style frosted look (PlayerBar, BottomNav,
overflow menu, bottom sheets, modal backdrops) reuse the glass
tokens from `tokens.css`: fixed strips use `--glass-backdrop-fixed`
(and `--glass-backdrop-fixed-player` on the player bar); sticky bars
and sheets combine `--glass-blur-*` with `--glass-saturate`. When
`prefers-reduced-motion` or `prefers-reduced-data` applies,
`installGlassPerformanceClass()` adds `ds-low-glass` on
`<html>` and heavy backdrop filters fall back to opaque surfaces.

## Global error states

Fatal React errors (error boundary) and long-running lazy-route loads
(Suspense timeout) use `AppErrorFallback`
(`frontend/src/components/AppErrorFallback.tsx`): UI is rendered via
**`createPortal` → `document.body`** inside `.app-issue-overlay`
(`position: fixed`, `--z-modal`) so taps are not swallowed by the fixed
player bar / bottom nav above `#main`. Centered `.app-issue-panel` in
`frontend/src/styles/global.css`, `alert-triangle` icon, title + short
hint, primary action via `MotionPress`. The route `ErrorBoundary` bumps a
`Fragment` **key** on retry to remount the subtree. Copy lives in
`frontend/src/locales/i18n_extra_*.json` under `app.errorTitle`,
`app.errorHint`, `app.sectionLoadError`, `app.sectionLoadHint`.

## UI primitives

### `Press`

Accessible button with built-in tap target, focus ring and
press-state animation.

```tsx
<Press variant="primary" iconOnly={false}>Save</Press>
<Press variant="icon" aria-label="Закрыть">
  <Icon name="x" size={18} />
</Press>
```

### `Sheet`

Bottom sheet with swipe-down dismiss, Escape support and a visible
drag handle. Uses CSS transitions only (no Framer Motion).

```tsx
<Sheet open={open} onClose={close} ariaLabel="Now playing">
  …
</Sheet>
```

### `EmptyState`

Standard empty/error layout with a stroke icon, title, hint and
optional CTA.

```tsx
<EmptyState
  icon="empty-staff"
  title="Лайков пока нет"
  hint="Поставь сердечко на любимом треке"
/>
```

### `SkeletonList`

Six-row shimmer placeholder for list views during initial load.

### `OfflineBanner`

Renders a pill banner at the top of the screen whenever
`navigator.onLine` is false. Mounted once in `App.tsx`.

## Iconography

All icons are defined in `frontend/src/components/Icon/Icon.tsx`,
stroke-only, sharing the 24×24 view-box. Whenever a component is
about to use a Unicode glyph or an emoji, replace it with an
`<Icon name="…" />` call. New glyphs (for example `calendar` for
date-scoped content) are added to the same `PATHS` map.

## Status semantics (admin only)

The strict monochrome rule has **one** documented exception: the
status indicators in the admin panel. A monochrome status pill is
indistinguishable at a glance, which is unsafe for an
operations-facing surface.

Three semantic tokens live in `global.css`:

| Token              | Color           | Used for                                |
| ------------------ | --------------- | --------------------------------------- |
| `--state-ok`       | `#34C759` (green)  | healthy / running / success            |
| `--state-warn`     | `#FFCC00` (amber)  | open complaints / pending devices      |
| `--state-error`    | `#FF453A` (red)    | failed / unhealthy / locked-out        |
| `--state-unknown`  | neutral grey       | unknown / not applicable               |

These tokens are **only** consumed by `<StatusPill>` and
`<KpiCard accent="warn"|"error">` inside `frontend/src/admin/`.
The rest of the UI keeps the strict monochrome palette. Do not
reach for these tokens from regular user-facing components.

## Admin components

The admin chunk under `frontend/src/admin/` ships its own narrow
set of building blocks on top of the design system:

- `StatusPill` — color-aware status badge (see above).
- `KpiCard` — large numeric KPI with label/hint, used on the
  dashboard.
- `DataTable` — server-side pagination/sort wrapper around
  `@tanstack/react-table`.
- `LineChart` — `recharts` area chart pre-styled with
  `currentColor` and the project surface tokens.
- `JsonViewer` — read-only `<pre>`-based JSON dump for audit
  payloads.
- `LiveLogStream` — virtualized list rendered from the Loki
  query endpoint.
- `TotpInput` / `StepUpDialog` — TOTP UX primitives.

These components live next to the admin routes, not under
`frontend/src/components/ui/`, because they depend on
`@tanstack/react-query` + `recharts` + `qrcode` which the public
Mini App must not pay for.

## Telegram-native helpers

`frontend/src/lib/telegram.ts` exposes:

- On load (after `ready` / `expand`), calls Telegram
  `disableVerticalSwipes()` so a downward swipe on page content does
  not minimize or close the Mini App (Bot API 7.7+). Users can still
  dismiss via the Telegram header strip.
- `installTelegramThemeBridge()` — once per session.
- `installViewportListener()` — keeps `--vh` in sync with the
  Telegram viewport.
- `setBackButton(visible, onClick)` — wires the native back button
  to a navigation callback. Returns a cleanup function.
- `haptic('light' | 'medium' | 'heavy')` — impact feedback for
  buttons.
- `hapticNotification('success' | 'warning' | 'error')` —
  notification haptics for completed actions.

## Artist catalog (Mini App)

Release cards in `ArtistView` use `.artist-catalog-release-card`.
SoundCloud artist-station rows add
`.artist-catalog-release-card-station` and an inline
`.artist-catalog-release-station-badge` (monochrome caption
below meta; styles in `frontend/src/styles/global.css`).

Popular tracks on the redesigned artist page use
`.rf-artist-top-tracks*` in `frontend/src/styles/redesign-artist.css`:
horizontal snap slides of three `TrackCard` rows (swipe on touch;
`useHorizontalPointerDragScroll` adds mouse drag (`pointerdown` capture on
the scroller + `window` `pointermove` / `pointerup`, and horizontal /
Shift+`wheel`) on fine pointers; snap-to-page uses
`lib/horizontalScrollAnimate.ts` (`requestAnimationFrame` + ease-out,
WebView-safe) instead of `scrollTo({ behavior: 'smooth' })`. Arrow buttons
use the same helper. Respects `prefers-reduced-motion`;
`h-snap__arrow` controls only on `≥768px` + fine pointer), optional
page dots, and a bottom-sheet modal (`.rf-artist-tracks-modal`) for
the full list with the standard `TrackList` + `SwipeRow` pattern.

Catalog releases on the same page use `.rf-artist-releases*` with the
same carousel mechanics (three `.artist-catalog-release-card` rows per
slide; fine-pointer mouse drag via the same hook) and
`.rf-artist-releases-modal` for the full list. The section
heading is `artist.catalog_releases_title` (“Релизы” / “Releases”) with
a count; `release_kind === dotsound_sc_artist_station` rows are sorted
first and their card title uses `redesign.artist.catalogReleasesSimilar`
(“Похожее: {name}”), then other releases follow in API order.

Artist header shows monthly listeners in a compact inline row
`.artist-monthly-listeners-inline` under the name/meta line with a
stroke icon (`users-listeners`). Keep it monochrome, compact and
non-intrusive.

## Track card extras

`TrackCardSheet` exposes advanced playback controls through a
dedicated bottom-sheet overlay (`.tcs-extras-overlay` /
`.tcs-extras-sheet`) opened from the action grid button
`trackSheet.more`. Do not render these controls in transparent floating
popovers over core playback controls.

Spacing in the track card should keep side gutters at `24px` for
primary content blocks (`.tcs-info`, `.tcs-player-controls`,
`.tcs-actions`, `.tcs-edit-panel`) to avoid text and controls sticking
to card edges.

List-style `TrackCard` rows (feeds, playlists, history, liked/disliked):
cover, title on the first line, optional artist on the next (`.track-card-artist`;
`.track-card-artist--nav` on desktop fine pointer opens the artist page via
`useNavigateToArtistByName`, same breakpoint as `PlayerBar`), and a single muted
summary line
(`.track-card-meta.track-card-summary`) built by `buildTrackCardSummaryLine`
in `lib/trackCardFormat.ts` — duration, human-readable source label, then
contextual time when present (last listen, liked-at, disliked-at).
Default list scale (all viewports): `.re-tc-cover-wrap` is `56×56`
(`58×58` at `≤560px`, `54×54` at `≤360px`), `.track-card` padding
`14×22` (`12×14` on narrow phones, `14×26` from `768px`), title
`fs-15`, summary `fs-12`, row gap `18px`. `CoverImage` defaults to
`56×56` so inline covers match list cards. Legacy `.track-source` link
blocks stay hidden on narrow viewports.
Platform/catalog badges are not shown on the title row except
`.track-badge-private` and owner-only moderation state. `#main` keeps
extra bottom padding so the last rows clear the fixed player + tab bar.

Search results for not-yet-imported YouTube / Bandcamp / SoundCloud rows
use `SearchPendingTrackRow` in `SearchView.tsx`: same `re-tc-main` row,
`re-tc-cover-wrap` thumbnail, title then artist line, summary line
(duration · platform · `search.addAndPlay`), and `MotionPress` +
`MorphIcon` heart like list `TrackCard`.

The third-party stream access label (`trackCard.accessStream`) is not
shown on list rows; it appears in `TrackCardSheet` inside
`.tcs-source-info` as `.tcs-access-mode-line` when
`access_mode === third_party_stream` (with source link + disclaimer when
URLs exist).

## Migration playbook

1. Replace literal spacing with `--space-*`.
2. Replace literal duration values with `--dur-*` and easing.
3. Replace bespoke colour values with the monochrome tokens.
4. Use `MotionPress` (not bare `<button>`) for every interactive
   button in redesigned surfaces.
5. Use `showIsland()` / `dismissIsland()` from `lib/island` instead
   of `useToast()` for all user-facing notifications. `Toast` /
   `useToast` are retained for legacy surfaces only and should not
   be used in new code.
6. Run `npx tsc --noEmit` and the visual smoke test before
   committing.

## Redesign 2026 primitives

The big-bang iOS-style redesign (branch `redesign/ios-2026`) adds
a new layer of primitives in `frontend/src/components/ui/` powered
by `framer-motion`. Strict monochrome and `prefers-reduced-motion`
rules continue to apply. Single source of truth for shared APIs is
`docs/redesign-2026/SHARED-CONTRACTS.md` — do not duplicate that
document here.

Highlights:

- `MotionPress` — spring-button replacement for `Press` in new
  surfaces; variants `primary | ghost | icon | subtle`, integrates
  Telegram haptics.
- `MorphIcon` — outline ↔ filled icon morph for `heart`, `play`,
  `pause`, `star`, `bookmark`, `home`, `search`, `library`,
  `chats`, `profile`, `radio`, `users-following`, `flame`.
- `SwipeRow` — left/right swipe-actions row with rubber-band and
  threshold-armed haptic.
- `LongPressMenu` — iOS-style context menu over any trigger; overlay is
  portaled to `document.body` so it stays above nested transforms
  (e.g. `SwipeRow` drag) and keeps correct hit-testing on desktop.
- `DynamicIslandHost` + `lib/island.ts` — single top-of-screen
  pill for toasts, progress, now-playing, errors. Use
  `showIsland()` / `dismissIsland()` from `lib/island`.
- `AmbientStage` — three-layer radial gradient backdrop driven by
  `lib/coverPalette.ts` (32×32 downsample, top-3 clusters,
  desaturated to monochrome).
- `KenBurnsCover` — slow pan/zoom over a still cover image.
- `BeatPulse` — phase-locked subtle pulse driven by BPM.
- `HorizontalSnap` — accessible snap-carousel with optional dots,
  arrows on `≥md`, and per-card parallax.
- `SharedCover` — wrapper + `m.img` (`layoutId={cover-${trackId}}`)
  for shared-element transitions between PlayerBar, NowPlaying and
  TrackCard; gradient frame until `onLoad`, then image fades in.
- `AdminRangeSwitch` — segmented control for admin surfaces.
  Uses `LayoutGroup` + `layoutId` pill indicator (Framer Motion),
  `MotionPress` per option, `role="tablist"`, `prefers-reduced-motion`
  aware. Lives in `frontend/src/admin/components/widgets/`.

Motion presets live in `frontend/src/lib/motion.ts`
(`SPRING_GENTLE/SNAPPY/BOUNCY/LAYOUT`, `TWEEN_FAST/SLOW`, plus
`VARIANTS_FADE_UP/SCALE_IN/PAGE_SLIDE/SHEET_SLIDE_UP`). The app
is wrapped in `<LazyMotion features={domAnimation}>` so consumers
import the lowercase `m` alias instead of `motion` to keep the
bundle small.

Typography: the redesign keeps the strict monochrome palette but
swaps the body `font-family` to a system-ui cascade
(`--font-stack-system` — SF Pro on iOS, Roboto on Android). New
display-scale tokens `--fs-lt: 34px`, `--fs-tt: 28px` and
negative letter-spacing tokens (`--ls-display`, `--ls-tight`,
`--ls-snug`) bring Apple-style large titles.

CSS scaffolding lives in `frontend/src/styles/redesign-shared.css`
(primitives) plus per-stage placeholders
(`redesign-player.css`, `redesign-nav.css`, …). All scaffolds are
imported once from `main.tsx`.

