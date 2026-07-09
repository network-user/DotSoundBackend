import { useEffect } from 'react'

const STORAGE_PREFIX = 'main-scroll:'

// Cap the restore retry loop (~1.2s at 60fps) so it never spins
// forever when the saved offset is unreachable — e.g. a shorter
// result set after a new search, or a feed whose lazy sections
// simply do not add up to the previous height.
const MAX_RESTORE_FRAMES = 72

function readSaved(storageKey: string): number {
  try {
    const raw = sessionStorage.getItem(storageKey)
    return raw ? Number(raw) : NaN
  } catch {
    return NaN
  }
}

/**
 * Saves and restores the scroll position of the shared `#main`
 * container under a session-scoped `key`.
 *
 * `#main` is the app's real scroll root; `window.scrollTo` and
 * react-router `<ScrollRestoration>` are silent no-ops here, which is
 * why restoration has to target this element directly.
 *
 * Restore is resilient to late-loading content: instead of clamping
 * against a still-short page on the first frame, it retries on
 * animation frames until `#main` is tall enough to reach the saved
 * offset (or the frame budget runs out). Positions the loop sets
 * while waiting are not persisted, so a transient clamp can't
 * overwrite the real target.
 *
 * The `key` is the caller's content identity: reusing the same key
 * (e.g. returning to a view via the back button) restores; a fresh
 * key (a new search query, a different library tab) starts clean.
 * Passing `null` disables the hook entirely.
 */
export function useMainScrollRestore(key: string | null): void {
  useEffect(() => {
    if (!key) return
    const main = document.getElementById('main')
    if (!main) return

    const storageKey = `${STORAGE_PREFIX}${key}`

    let restoreRaf = 0
    let saveRaf = 0

    const targetY = readSaved(storageKey)
    if (Number.isFinite(targetY) && targetY > 0) {
      let frames = 0
      const step = () => {
        frames += 1
        const maxScroll = main.scrollHeight - main.clientHeight
        if (maxScroll >= targetY - 1) {
          main.scrollTop = targetY
          restoreRaf = 0
          return
        }
        if (frames >= MAX_RESTORE_FRAMES) {
          main.scrollTop = Math.max(0, maxScroll)
          restoreRaf = 0
          return
        }
        restoreRaf = requestAnimationFrame(step)
      }
      restoreRaf = requestAnimationFrame(step)
    }

    const onScroll = () => {
      // Ignore the scroll events our own restore loop produces while
      // it is still waiting for content to grow.
      if (restoreRaf !== 0 || saveRaf !== 0) return
      saveRaf = requestAnimationFrame(() => {
        saveRaf = 0
        try {
          sessionStorage.setItem(
            storageKey,
            String(Math.round(main.scrollTop)),
          )
        } catch {
          /* quota / privacy mode — ignore */
        }
      })
    }

    main.addEventListener('scroll', onScroll, { passive: true })

    return () => {
      if (restoreRaf !== 0) cancelAnimationFrame(restoreRaf)
      if (saveRaf !== 0) cancelAnimationFrame(saveRaf)
      main.removeEventListener('scroll', onScroll)
    }
  }, [key])
}
