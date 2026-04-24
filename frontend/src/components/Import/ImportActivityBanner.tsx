import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { ImportJobResponse } from '@/types/api'

const ACTIVE = new Set([
  'scanning',
  'ready',
  'queued',
  'importing',
])

function labelFor(
  j: ImportJobResponse,
): { line: string; sub?: string } {
  if (j.status === 'scanning') {
    if (j.source === 'yandex_music') {
      return { line: 'Сканируем Яндекс.Музыку…' }
    }
    if (
      j.source === 'spotify' ||
      j.source === 'soundcloud_playlist'
    ) {
      return { line: 'Сканируем плейлист…' }
    }
    return { line: 'Ищем треки в Telegram…' }
  }
  if (j.status === 'ready') {
    return {
      line: 'Выберите треки',
      sub: 'Профиль → Импорт',
    }
  }
  if (j.status === 'queued') {
    return {
      line: 'Импорт в очереди',
      sub: j.queue_position
        ? `Позиция ${j.queue_position}`
        : undefined,
    }
  }
  if (j.status === 'importing') {
    const max = j.total_tracks || 0
    const done = j.completed_tracks + j.failed_tracks
    return {
      line: 'Импортируем',
      sub: max
        ? `${Math.min(done, max)} / ${max}`
        : undefined,
    }
  }
  return { line: 'Импорт' }
}

export function ImportActivityBanner() {
  const [job, setJob] = useState<ImportJobResponse | null>(null)

  useEffect(() => {
    if (!api.getToken()) return
    const poll = () => {
      api
        .getActiveImport()
        .then(j => {
          if (j && ACTIVE.has(j.status)) {
            setJob(j)
          } else {
            setJob(null)
          }
        })
        .catch(() => setJob(null))
    }
    poll()
    const id = window.setInterval(poll, 3000)
    return () => window.clearInterval(id)
  }, [])

  if (!job) return null

  const { line, sub } = labelFor(job)
  const max = job.total_tracks || 0
  const done = job.completed_tracks + job.failed_tracks
  const pct =
    job.status === 'importing' && max > 0
      ? Math.min(100, (done / max) * 100)
      : null

  return (
    <div
      className="import-activity-banner"
      role="status"
      aria-live="polite"
    >
      <div className="import-activity-banner__row">
        <div className="import-activity-banner__shimmer" />
        <div className="import-activity-banner__text">
          <span className="import-activity-banner__line">
            {line}
          </span>
          {sub && (
            <span className="import-activity-banner__sub">
              {sub}
            </span>
          )}
        </div>
      </div>
      {pct != null && (
        <div
          className="import-activity-banner__bar"
          aria-hidden
        >
          <div
            className="import-activity-banner__bar-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  )
}
