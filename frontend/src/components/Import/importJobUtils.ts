import type {
  ImportAudioInfo,
  ImportExternalTrackInfo,
  ImportJobResponse,
} from '@/types/api'

export const MAX_FILE_SIZE = 20 * 1024 * 1024

export const EXTERNAL_SOURCES = new Set([
  'yandex_music',
  'spotify',
  'soundcloud_playlist',
])

export function normalizeJobTracks(
  job: ImportJobResponse,
): ImportAudioInfo[] {
  const data = job.tracks_data
  if (!data) return []
  if (EXTERNAL_SOURCES.has(job.source)) {
    const tracks: ImportExternalTrackInfo[] = data.tracks || []
    return tracks.map((t, i) => ({
      file_id: `${job.source}:${i}`,
      title: t.title,
      performer: t.artist,
      duration: t.duration_seconds,
      file_size: null,
    }))
  }
  return data.audios || []
}

export function defaultSelectedIndices(
  list: ImportAudioInfo[],
): Set<number> {
  return new Set(
    list
      .map((_, i) => i)
      .filter(
        (i) =>
          !list[i].file_size ||
          list[i].file_size! <= MAX_FILE_SIZE,
      ),
  )
}

export function fmtDuration(sec: number | null): string {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

export function fmtSize(bytes: number | null): string {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(1)} МБ`
}

export function scanningLabel(
  source: string | undefined,
): string {
  if (source === 'yandex_music') {
    return 'Сканируем плейлист Яндекс Музыки...'
  }
  if (EXTERNAL_SOURCES.has(source || '')) {
    return 'Сканируем плейлист...'
  }
  return 'Ищем треки в вашем профиле Telegram...'
}
