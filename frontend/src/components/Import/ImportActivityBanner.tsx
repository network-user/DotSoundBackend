import {
  useCallback,
  useEffect,
  useState,
  type MouseEvent,
} from 'react'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type { ImportJobResponse } from '@/types/api'

/** Only real background work. `ready` / `scanning` belong in Профиль → Импорт. */
const ACTIVE = new Set(['queued', 'importing'])

const DISMISS_JOB_KEY = 'dotsound_import_activity_banner_dismiss_job_id'

function readDismissedJobId(): number | null {
  const s = sessionStorage.getItem(DISMISS_JOB_KEY)
  if (s == null) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

function labelFor(
  j: ImportJobResponse,
): { line: string; sub?: string } {
  if (j.status === 'queued') {
    return {
      line: 'В очереди',
      sub: j.queue_position
        ? `№ ${j.queue_position}`
        : undefined,
    }
  }
  if (j.status === 'importing') {
    const max = j.total_tracks || 0
    const done = j.completed_tracks + j.failed_tracks
    return {
      line: 'Импорт',
      sub: max
        ? `${Math.min(done, max)} / ${max}`
        : undefined,
    }
  }
  return { line: 'Импорт' }
}

export function ImportActivityBanner() {
  const [job, setJob] = useState<ImportJobResponse | null>(null)
  const [dismissedJobId, setDismissedJobId] = useState<number | null>(
    readDismissedJobId,
  )

  const clearDismiss = useCallback(() => {
    sessionStorage.removeItem(DISMISS_JOB_KEY)
    setDismissedJobId(null)
  }, [])

  useEffect(() => {
    if (!api.getToken()) return
    const poll = () => {
      api
        .getActiveImport()
        .then(j => {
          if (j && ACTIVE.has(j.status)) {
            const stored = readDismissedJobId()
            if (stored != null && j.id !== stored) {
              clearDismiss()
            }
            setJob(j)
          } else {
            setJob(null)
            if (readDismissedJobId() != null) {
              clearDismiss()
            }
          }
        })
        .catch(() => {
          setJob(null)
        })
    }
    poll()
    const id = window.setInterval(poll, 3000)
    return () => window.clearInterval(id)
  }, [clearDismiss])

  const handleDismiss = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    if (!job) return
    sessionStorage.setItem(DISMISS_JOB_KEY, String(job.id))
    setDismissedJobId(job.id)
  }

  if (!job) return null
  if (dismissedJobId != null && job.id === dismissedJobId) {
    return null
  }

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
        <button
          type="button"
          className="import-activity-banner__dismiss"
          onClick={handleDismiss}
          aria-label="Скрыть уведомление; импорт продолжится в фоне"
        >
          <Icon name="x" size={16} />
        </button>
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
