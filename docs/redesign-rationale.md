# DotSound Mini App — Redesign Rationale

## Problems we set out to solve

- "Кнопки съехали и не продуманы" (verbatim user feedback). The
  player bar packed eight controls into a single row that did not
  fit on small phones.
- iPhone safe-area was missing on the bottom UI; controls were
  partially obscured by the home indicator.
- The progress bar in the player did not visually update on
  WebKit because the `--progress` CSS variable was never set.
- The PWA layer was wired in `vite.config.ts` but `main.tsx` was
  unconditionally unregistering every service worker, leaving the
  app effectively non-PWA.
- Three player contexts existed but every consumer subscribed to
  the legacy aggregated context, causing the entire UI to
  re-render on every `currentTime` tick.
- Several screens used Unicode glyphs (`⏮ ⏸ ▶ ⏭ ▤ ＋ × ←`) instead
  of the project's stroke-icon set.
- Telegram-native UX (BackButton, HapticFeedback, themeChanged,
  viewportChanged) was unused.
- a11y debt: most icon-only buttons had no `aria-label`,
  `outline:none` was global without a `:focus-visible` substitute,
  and modals had no Escape support.

## Direction

**Linear/Apple HIG monochrome minimalism + Telegram-native +
limited Spotify pattern for the player.**

This was the only direction that matched the existing project
rules ("минимализм, монохром, stroke-иконки", AGENTS.md) without
introducing colour, drop shadows or new fonts. Telegram-native
gives the Mini App a "first-party" feel inside the messenger,
while the Spotify "mini player → bottom sheet" pattern lets us
keep the player bar uncluttered without sacrificing power-user
features.

## Player bar — before vs after

**Before:** one row, eight visible controls, no overflow, the
secondary actions (EQ, shuffle, repeat, stop) shipped to mobile
even when the screen was 320 px wide.

**After:**

- Mobile (≤480 px): mini bar with cover, title/artist,
  next/play and a single `⋯` overflow button. Like, prev, EQ,
  shuffle, repeat and stop now live inside the overflow menu.
- Tablet (481–1023 px): adds prev and like to the visible row.
- Desktop (≥1024 px): three-zone floating bar (meta /
  transport / secondary), 320 px on each side.
- The scrubber sits inside a 24 px tall hit-zone but the visible
  track stays 6 px tall. The fill is rendered with a
  `linear-gradient` driven by `--progress`, so WebKit and
  Firefox now show the same progress.
- All transport buttons trigger `HapticFeedback.impactOccurred`
  when running inside Telegram.

## Other notable decisions

- **Safe area:** every fixed-bottom element now uses
  `env(safe-area-inset-bottom)` either directly or via
  `--safe-bottom`.
- **Splash:** the previous hard-coded 1800 ms loader is replaced
  by an `app-ready` event with a 1200 ms safety cap.
- **Skeleton/Empty/Offline states:** centralised primitives in
  `frontend/src/components/ui/`.
- **`useConfirm`:** the dangling helper has been promoted to a
  documented primitive with proper unmount cleanup; recommended
  for delete-track and clear-EQ confirmations.
- **PrivateCore black-box exception:** the existing `lyrics_provider`
  and `artist_info_provider` cascades were formally legalised as
  bounded transport exceptions in
  `DotSoundPrivateCore/docs/ai-boundary-policy.md`, instead of
  silently violating the rule.

## What we deliberately did not do

- No Framer Motion, no Tailwind, no design-token JSON pipeline.
  The system stays plain CSS variables to keep the bundle small.
- No offline-cache for audio (still in TODO).
- No gapless audio prefetch on the frontend (also in TODO).
- No big React Query rollout — only the foundations are in place,
  endpoint migration happens incrementally.
