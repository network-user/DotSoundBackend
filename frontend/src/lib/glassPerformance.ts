export function installGlassPerformanceClass(): void {
  if (typeof document === 'undefined') return
  const reducedMotion = window.matchMedia(
    '(prefers-reduced-motion: reduce)',
  ).matches
  const reducedData = window.matchMedia(
    '(prefers-reduced-data: reduce)',
  ).matches
  if (reducedMotion || reducedData) {
    document.documentElement.classList.add('ds-low-glass')
  }
}
