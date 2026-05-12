import type { SyncedLine } from '@/types/api'

export interface UploadAudioFileMeta {
  name: string
  size: number
  lastModified: number
}

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
  audioFileMeta?: UploadAudioFileMeta | null
}

export const UPLOAD_DRAFT_STORAGE_KEY = 'dotsound:upload-draft:v1'
export const UPLOAD_DRAFT_CHANGED_EVENT = 'dotsound:upload-draft-changed'
const KEY = UPLOAD_DRAFT_STORAGE_KEY
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
    window.dispatchEvent(new Event(UPLOAD_DRAFT_CHANGED_EVENT))
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
    window.dispatchEvent(new Event(UPLOAD_DRAFT_CHANGED_EVENT))
  } catch {
    /* noop */
  }
}

export function hasMeaningfulDraft(draft: UploadDraft): boolean {
  const hasAudioHint = Boolean(
    draft.audioFileMeta &&
      (draft.audioFileMeta.name.trim().length > 0 ||
        draft.audioFileMeta.size > 0),
  )
  return Boolean(
    hasAudioHint ||
      draft.stepIndex > 0 ||
      draft.title.trim() ||
      draft.artistName.trim() ||
      draft.genre.trim() ||
      draft.lyricsPlainText.trim() ||
      (draft.lyricsSyncedLines && draft.lyricsSyncedLines.length),
  )
}
