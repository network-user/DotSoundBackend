import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import type {
  ImportAudioInfo,
  ImportExternalTrackInfo,
  ImportJobResponse,
} from '@/types/api'
import { ImportSourcePicker } from './ImportSourcePicker'
import { YandexMusicUrlModal } from './YandexMusicUrlModal'

type AudioInfo = ImportAudioInfo
type ImportJobData = ImportJobResponse

type Phase = 'pick' | 'scanning' | 'select' | 'importing' | 'done'

const MAX_FILE_SIZE = 20 * 1024 * 1024

const EXTERNAL_SOURCES = new Set([
  'yandex_music',
  'spotify',
  'soundcloud_playlist',
])

function fmtDuration(sec: number | null): string {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function fmtSize(bytes: number | null): string {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(1)} МБ`
}

function normalizeJobTracks(job: ImportJobData): AudioInfo[] {
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

function scanningLabel(source: string | undefined): string {
  if (source === 'yandex_music') {
    return 'Сканируем плейлист Яндекс Музыки...'
  }
  if (EXTERNAL_SOURCES.has(source || '')) {
    return 'Сканируем плейлист...'
  }
  return 'Ищем треки в вашем профиле Telegram...'
}

export function ImportView({ active }: { active: boolean }) {
  const [phase, setPhase] = useState<Phase>('pick')
  const [job, setJob] = useState<ImportJobData | null>(null)
  const [audios, setAudios] = useState<AudioInfo[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [yandexModalOpen, setYandexModalOpen] = useState(false)
  const pollCountRef = useRef(0)
  const MAX_POLLS = 150

  useEffect(() => {
    if (!active) return
    api.getActiveImport().then((j) => {
      if (j && j.status === 'importing') {
        setJob(j)
        setPhase('importing')
      } else if (j && j.status === 'ready') {
        setJob(j)
        const list = normalizeJobTracks(j)
        setAudios(list)
        const all = new Set<number>(
          list
            .map((_, i) => i)
            .filter((i) => {
              const a = list[i]
              return !a.file_size || a.file_size <= MAX_FILE_SIZE
            })
        )
        setSelected(all)
        setPhase('select')
      }
    }).catch(() => {})
  }, [active])

  useEffect(() => {
    if (phase !== 'importing' || !job) return
    pollCountRef.current = 0
    const interval = setInterval(async () => {
      pollCountRef.current++
      if (pollCountRef.current > MAX_POLLS) {
        clearInterval(interval)
        setError('Импорт занял слишком много времени. Попробуйте позже.')
        setPhase('pick')
        return
      }
      try {
        const updated = await api.getImportStatus(job.id)
        setJob(updated)
        if (updated.status === 'done' || updated.status === 'cancelled') {
          setPhase('done')
          clearInterval(interval)
        }
      } catch {}
    }, 2000)
    return () => clearInterval(interval)
  }, [phase, job?.id])

  const applyScanResult = useCallback((j: ImportJobData): boolean => {
    setJob(j)
    if (j.status === 'failed') {
      return false
    }
    const list = normalizeJobTracks(j)
    setAudios(list)
    const all = new Set<number>(
      list
        .map((_, i) => i)
        .filter((i) => !list[i].file_size || list[i].file_size! <= MAX_FILE_SIZE)
    )
    setSelected(all)
    setPhase('select')
    return true
  }, [])

  const handleSourceSelect = useCallback(async (sourceId: string) => {
    setError(null)
    if (sourceId === 'yandex') {
      setYandexModalOpen(true)
      return
    }
    if (sourceId !== 'telegram') return
    setPhase('scanning')
    try {
      const j = await api.startTelegramImport()
      if (!applyScanResult(j)) {
        setError('Не удалось получить треки из профиля')
        setPhase('pick')
      }
    } catch {
      setError('Ошибка подключения к боту')
      setPhase('pick')
    }
  }, [applyScanResult])

  const handleYandexScan = useCallback(async (url: string) => {
    setError(null)
    setPhase('scanning')
    try {
      const j = await api.startYandexMusicImport(url)
      if (j.status === 'failed') {
        const code = j.tracks_data?.error_code
        const msg =
          code === 'not_found'
            ? 'Плейлист или альбом не найден'
            : code === 'private'
              ? 'Плейлист закрыт или требует авторизации'
              : code === 'invalid_url'
                ? 'Ссылка не распознана как плейлист Яндекс Музыки'
                : 'Не удалось получить список треков. Попробуйте позже.'
        setPhase('pick')
        throw new Error(msg)
      }
      applyScanResult(j)
      setYandexModalOpen(false)
    } catch (e) {
      setPhase('pick')
      throw e
    }
  }, [applyScanResult])

  const toggleTrack = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const selectAll = () => {
    const all = new Set<number>(
      audios.map((_, i) => i)
        .filter((i) => !audios[i].file_size || audios[i].file_size! <= MAX_FILE_SIZE)
    )
    setSelected(all)
  }

  const deselectAll = () => setSelected(new Set())

  const handleStartImport = async () => {
    if (!job) return
    try {
      const updated = await api.startImportJob(job.id, Array.from(selected))
      setJob(updated)
      setPhase('importing')
    } catch {
      setError('Не удалось запустить импорт')
    }
  }

  const handleReset = () => {
    setPhase('pick')
    setJob(null)
    setAudios([])
    setSelected(new Set())
    setError(null)
    pollCountRef.current = 0
  }

  if (!active) return null

  return (
    <div className="import-view">
      {error && (
        <div className="form-error" style={{ margin: '16px' }}>{error}</div>
      )}

      {phase === 'pick' && (
        <ImportSourcePicker onSelect={handleSourceSelect} />
      )}

      {phase === 'scanning' && (
        <div className="import-scanning">
          <div className="loader" />
          <p className="empty-hint">{scanningLabel(job?.source)}</p>
        </div>
      )}

      {phase === 'select' && (
        <div className="import-select">
          <div className="view-header">
            <h2>Найдено треков: {audios.length}</h2>
            <span className="hint">Выбери треки для импорта</span>
          </div>

          <div className="import-select-actions">
            <button className="btn-secondary" onClick={selectAll}>Выбрать все</button>
            <button className="btn-secondary" onClick={deselectAll}>Снять все</button>
          </div>

          <div className="import-track-list">
            {audios.map((audio, i) => {
              const tooBig = audio.file_size != null && audio.file_size > MAX_FILE_SIZE
              return (
                <label
                  key={audio.file_id || i}
                  className={`import-track-item${tooBig ? ' disabled' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(i)}
                    disabled={tooBig}
                    onChange={() => toggleTrack(i)}
                  />
                  <div className="import-track-info">
                    <span className="import-track-title">{audio.title}</span>
                    <span className="import-track-meta">
                      {audio.performer || 'Неизвестный'}
                      {audio.duration ? ` · ${fmtDuration(audio.duration)}` : ''}
                      {audio.file_size ? ` · ${fmtSize(audio.file_size)}` : ''}
                    </span>
                    {tooBig && (
                      <span className="import-track-warning">Файл слишком большой (макс. 20 МБ)</span>
                    )}
                  </div>
                </label>
              )
            })}
          </div>

          <div style={{ padding: '16px' }}>
            <button
              className="btn-primary"
              disabled={selected.size === 0}
              onClick={handleStartImport}
            >
              Импортировать ({selected.size})
            </button>
          </div>
        </div>
      )}

      {phase === 'importing' && job && (
        <div className="import-progress">
          <div className="view-header">
            <h2>Импорт...</h2>
            <span className="hint">
              {job.completed_tracks + job.failed_tracks} / {job.total_tracks}
            </span>
          </div>
          <div className="progress-bar-wrap" style={{ margin: '0 16px' }}>
            <div
              className="progress-bar-fill"
              style={{
                width: job.total_tracks
                  ? `${((job.completed_tracks + job.failed_tracks) / job.total_tracks) * 100}%`
                  : '0%',
              }}
            />
          </div>
          <p className="progress-label">
            Загружено: {job.completed_tracks} · Ошибок: {job.failed_tracks}
          </p>
          <p className="empty-hint">
            Можно закрыть окно — импорт продолжится в фоне
          </p>
        </div>
      )}

      {phase === 'done' && job && (
        <div className="import-done">
          <div className="view-header">
            <h2>Готово!</h2>
            <span className="hint">
              Импортировано {job.completed_tracks} из {job.total_tracks} треков
              {job.failed_tracks > 0 && ` (ошибок: ${job.failed_tracks})`}
            </span>
          </div>
          <div style={{ padding: '0 16px' }}>
            <button className="btn-primary" onClick={handleReset}>
              Импортировать ещё
            </button>
          </div>
        </div>
      )}

      <YandexMusicUrlModal
        open={yandexModalOpen}
        onClose={() => setYandexModalOpen(false)}
        onScan={handleYandexScan}
      />
    </div>
  )
}
