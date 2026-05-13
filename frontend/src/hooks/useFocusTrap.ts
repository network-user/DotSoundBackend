import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * Traps Tab navigation inside `containerRef` while `active` is true and
 * restores focus to the element that was focused right before activation
 * once it flips back to false.
 *
 * Designed for modals/sheets. Pair with role="dialog" + aria-modal.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
): void {
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!active) return
    previouslyFocusedRef.current =
      (document.activeElement as HTMLElement | null) ?? null

    const container = containerRef.current
    if (container) {
      const firstFocusable =
        container.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      if (firstFocusable) {
        firstFocusable.focus()
      } else if (container.tabIndex >= 0) {
        container.focus()
      }
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const root = containerRef.current
      if (!root) return
      const focusables = Array.from(
        root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((el) => !el.hasAttribute('aria-hidden'))
      if (focusables.length === 0) {
        e.preventDefault()
        return
      }
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const current = document.activeElement as HTMLElement | null
      if (e.shiftKey) {
        if (current === first || !root.contains(current)) {
          e.preventDefault()
          last.focus()
        }
      } else if (current === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKey)

    return () => {
      document.removeEventListener('keydown', onKey)
      const opener = previouslyFocusedRef.current
      previouslyFocusedRef.current = null
      if (opener && typeof opener.focus === 'function') {
        try {
          opener.focus()
        } catch {
          /* element may have been unmounted */
        }
      }
    }
  }, [active, containerRef])
}
