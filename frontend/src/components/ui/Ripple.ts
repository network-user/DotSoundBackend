import { useEffect, type RefObject } from 'react'

interface Options {
  disabled?: boolean
  color?: string
  duration?: number
}

const REDUCED_MOTION_QUERY =
  '(prefers-reduced-motion: reduce)'

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia(REDUCED_MOTION_QUERY)
      .matches
  } catch {
    return false
  }
}

/**
 * Attach a Material-style ripple to any host element.
 * Pure DOM, no React tree changes. Honours
 * prefers-reduced-motion. Cleans up on unmount.
 */
export function useRipple<T extends HTMLElement>(
  ref: RefObject<T>,
  { disabled, color, duration = 600 }: Options = {},
): void {
  useEffect(() => {
    if (disabled) return
    const host = ref.current
    if (!host) return
    host.classList.add('ripple-host')

    const handle = (e: PointerEvent) => {
      if (prefersReducedMotion()) return
      const rect = host.getBoundingClientRect()
      const size = Math.max(rect.width, rect.height) * 1.4
      const node = document.createElement('span')
      node.className = 'ripple'
      node.style.width = `${size}px`
      node.style.height = `${size}px`
      node.style.left = `${e.clientX - rect.left - size / 2}px`
      node.style.top = `${e.clientY - rect.top - size / 2}px`
      if (color) node.style.background = color
      host.appendChild(node)
      window.setTimeout(() => {
        node.remove()
      }, duration + 50)
    }

    host.addEventListener('pointerdown', handle)
    return () => {
      host.removeEventListener('pointerdown', handle)
    }
  }, [ref, disabled, color, duration])
}
