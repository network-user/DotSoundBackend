import type { RadioFreshness } from '@/types/api'

const cache = new Map<number, RadioFreshness>()
const MAX_ENTRIES = 500

export function rememberRadioFreshness(
  freshness: Record<number, RadioFreshness> | undefined,
): void {
  if (!freshness) return
  for (const [tid, label] of Object.entries(freshness)) {
    const id = Number(tid)
    if (!Number.isFinite(id)) continue
    cache.set(id, label)
  }
  while (cache.size > MAX_ENTRIES) {
    const oldest = cache.keys().next().value
    if (oldest === undefined) break
    cache.delete(oldest)
  }
}

export function getRadioFreshness(
  trackId: number,
): RadioFreshness | null {
  return cache.get(trackId) ?? null
}
