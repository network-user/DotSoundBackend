export const MIX_SHORTCUT_TILES = [
  {
    path: '/daily-mix',
    labelKey: 'quickDaily' as const,
    profileIcon: 'calendar',
    morph: 'calendar' as const,
  },
  {
    path: '/weekly-mix',
    labelKey: 'quickWeekly' as const,
    profileIcon: 'star',
    morph: 'star' as const,
  },
  {
    path: '/weekly-top',
    labelKey: 'quickTop' as const,
    profileIcon: 'flame',
    morph: 'flame' as const,
  },
  {
    path: '/user-choice',
    labelKey: 'quickUserChoice' as const,
    profileIcon: 'users-following',
    morph: 'heart' as const,
  },
  {
    path: '/forgotten-treasures',
    labelKey: 'quickForgotten' as const,
    profileIcon: 'music',
    morph: 'bookmark' as const,
  },
  {
    path: '/my-top',
    labelKey: 'quickMyTop' as const,
    profileIcon: 'chart',
    morph: 'star' as const,
  },
  {
    path: '/radio',
    labelKey: 'quickRadio' as const,
    profileIcon: 'radio',
    morph: 'radio' as const,
  },
] as const

export const HOME_QUICK_VISIBLE_COUNT = 4

export type MixShortcutTile =
  (typeof MIX_SHORTCUT_TILES)[number]
