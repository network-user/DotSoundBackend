function mediaMatches(query: string): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return false
  }
  try {
    return window.matchMedia(query).matches
  } catch {
    return false
  }
}

export function shouldUseLiteProfile(): boolean {
  if (typeof navigator === 'undefined') return false

  const nav = navigator as Navigator & {
    deviceMemory?: number
    connection?: {
      effectiveType?: string
      saveData?: boolean
    }
  }
  const cores = nav.hardwareConcurrency ?? 8
  const memoryGb = nav.deviceMemory ?? 8
  const effectiveType = nav.connection?.effectiveType ?? ''

  const isDesktop =
    mediaMatches('(hover: hover)') &&
    mediaMatches('(pointer: fine)')

  return (
    mediaMatches('(pointer: coarse)') ||
    mediaMatches('(hover: none)') ||
    mediaMatches('(prefers-reduced-data: reduce)') ||
    nav.connection?.saveData === true ||
    effectiveType === 'slow-2g' ||
    effectiveType === '2g' ||
    cores <= 4 ||
    memoryGb <= 4 ||
    (!isDesktop && cores <= 6)
  )
}

export function isPerfLiteActive(): boolean {
  if (typeof document === 'undefined') return false
  return (
    document.body?.classList.contains('ds-perf-lite') ||
    document.documentElement.classList.contains('ds-perf-lite')
  )
}

function toggleClass(name: string, enabled: boolean): void {
  document.documentElement.classList.toggle(name, enabled)
  document.body?.classList.toggle(name, enabled)
}

export function installGlassPerformanceClass(): void {
  if (typeof document === 'undefined') return

  const apply = () => {
    const reducedMotion = mediaMatches(
      '(prefers-reduced-motion: reduce)',
    )
    const reducedData = mediaMatches(
      '(prefers-reduced-data: reduce)',
    )
    const lowGlass = reducedMotion || reducedData
    toggleClass('ds-low-glass', lowGlass)
    toggleClass('ds-perf-lite', shouldUseLiteProfile())
  }

  apply()
  if (!document.body) {
    document.addEventListener('DOMContentLoaded', apply, {
      once: true,
    })
  }
}
