import type { SyncedLine } from '@/types/api'

export interface UploadDraft {
  v: 1
  savedAt: number
  stepIndex: number
  title: string
  artistMode: 'profile' | 'custom'
  artistName: string
  artistQuery: string
  genre: string
  genreQuery: string
  isPublic: boolean
  termsAccepted: boolean
  lyricsPlainText: string
  lyricsSyncedLines: SyncedLine[] | null
}

const KEY = 'dotsound:upload-draft:v1'
const TTL_MS = 48 * 60 * 60 * 1000

export function saveDraft(
  draft: Omit<UploadDraft, 'v' | 'savedAt'>,
): void {
  const payload: UploadDraft = {
    v: 1,
    savedAt: Date.now(),
    ...draft,
  }
  try {
    window.localStorage.setItem(KEY, JSON.stringify(payload))
  } catch {
    /* quota / disabled */
  }
}

export function loadDraft(): UploadDraft | null {
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(KEY)
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as UploadDraft
    if (parsed.v !== 1) return null
    if (Date.now() - parsed.savedAt > TTL_MS) {
      clearDraft()
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function clearDraft(): void {
  try {
    window.localStorage.removeItem(KEY)
  } catch {
    /* noop */
  }
}

export function hasMeaningfulDraft(draft: UploadDraft): boolean {
  return Boolean(
    draft.title.trim() ||
      draft.artistName.trim() ||
      draft.genre.trim() ||
      draft.lyricsPlainText.trim() ||
      (draft.lyricsSyncedLines && draft.lyricsSyncedLines.length),
  )
}
