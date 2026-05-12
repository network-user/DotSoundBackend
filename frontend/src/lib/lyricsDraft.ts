import type { SyncedLine } from '@/types/api'

export interface LyricsDraft {
  v: 1
  trackId: number
  plainText: string
  syncedLines: SyncedLine[] | null
  savedAt: number
}

const TTL_MS = 24 * 60 * 60 * 1000

function storageKey(trackId: number): string {
  return `dotsound:lyrics-draft:v1:${trackId}`
}

export function saveLyricsDraft(
  trackId: number,
  plainText: string,
  syncedLines: SyncedLine[] | null,
): void {
  const payload: LyricsDraft = {
    v: 1,
    trackId,
    plainText,
    syncedLines,
    savedAt: Date.now(),
  }
  try {
    window.localStorage.setItem(
      storageKey(trackId),
      JSON.stringify(payload),
    )
  } catch {
    /* quota / disabled */
  }
}

export function loadLyricsDraft(
  trackId: number,
): LyricsDraft | null {
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(storageKey(trackId))
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as LyricsDraft
    if (parsed.v !== 1) return null
    if (Date.now() - parsed.savedAt > TTL_MS) {
      clearLyricsDraft(trackId)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function clearLyricsDraft(trackId: number): void {
  try {
    window.localStorage.removeItem(storageKey(trackId))
  } catch {
    /* noop */
  }
}
