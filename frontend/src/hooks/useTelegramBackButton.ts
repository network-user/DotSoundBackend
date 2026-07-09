import { useEffect } from 'react'

import { setBackButton } from '@/lib/telegram'

/**
 * Shows the Telegram BackButton while the component is mounted and
 * wires `onBack` as its click handler.
 *
 * The button is removed via the cleanup returned by `setBackButton`,
 * which calls `offClick(onBack)` with the *same* handler reference
 * before hiding. This is what prevents handler leaks: the previous
 * per-view pattern called `setBackButton(false)` on unmount, which
 * only hid the button and left the stale `onClick` registered, so
 * handlers accumulated across navigations and fired for the wrong
 * screen.
 *
 * `onBack` should be stable (wrap it in `useCallback`); the button is
 * re-subscribed whenever `onBack` or `enabled` changes.
 */
export function useTelegramBackButton(
  onBack: () => void,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) {
      setBackButton(false)
      return
    }
    return setBackButton(true, onBack)
  }, [enabled, onBack])
}
