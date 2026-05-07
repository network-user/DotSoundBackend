import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import {
  dismissIsland,
  showIsland,
  updateIsland,
} from '@/lib/island'
import type { ImportJobResponse } from '@/types/api'

const ACTIVE = new Set(['queued', 'importing'])

const DISMISS_JOB_KEY = 'dotsound_import_activity_banner_dismiss_job_id'

const FOREGROUND_PERIOD_MS = 5000
const HIDDEN_PERIOD_MS = 30000

function readDismissedJobId(): number | null {
  const s = sessionStorage.getItem(DISMISS_JOB_KEY)
  if (s == null) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

interface IslandLabel {
  title: string
  hint?: string
  progress?: number
}

function buildLabel(
  job: ImportJobResponse,
  t: (key: string, opts?: Record<string, unknown>) => string,
): IslandLabel {
  if (job.status === 'queued') {
    return {
      title: t('redesign.upload.import.statusQueued'),
      hint: job.queue_position
        ? t('redesign.upload.import.queuePos', { n: job.queue_position })
        : undefined,
    }
  }
  const max = job.total_tracks || 0
  const done = job.completed_tracks + job.failed_tracks
  const progress = max > 0 ? Math.min(1, done / max) : undefined
  return {
    title: t('redesign.upload.import.statusImporting'),
    hint: max ? `${Math.min(done, max)} / ${max}` : undefined,
    progress,
  }
}

/**
 * Driver: subscribes to active import jobs and reflects their status into
 * the global DynamicIsland queue. Renders no DOM of its own.
 */
export function ImportActivityBanner() {
  const { t } = useTranslation()
  const [dismissedJobId, setDismissedJobId] = useState<number | null>(
    readDismissedJobId,
  )
  const islandIdRef = useRef<string | null>(null)
  const islandJobIdRef = useRef<number | null>(null)

  const clearIsland = () => {
    if (islandIdRef.current) {
      dismissIsland(islandIdRef.current)
      islandIdRef.current = null
      islandJobIdRef.current = null
    }
  }

  useEffect(() => {
    if (!api.getToken()) return

    let intervalId: number | null = null

    const periodMs = () =>
      document.visibilityState === 'visible'
        ? FOREGROUND_PERIOD_MS
        : HIDDEN_PERIOD_MS

    const onClickIsland = (jobId: number) => {
      sessionStorage.setItem(DISMISS_JOB_KEY, String(jobId))
      setDismissedJobId(jobId)
      clearIsland()
    }

    const reflect = (job: ImportJobResponse | null) => {
      if (!job || !ACTIVE.has(job.status)) {
        clearIsland()
        if (readDismissedJobId() != null) {
          sessionStorage.removeItem(DISMISS_JOB_KEY)
          setDismissedJobId(null)
        }
        return
      }
      const stored = readDismissedJobId()
      if (stored != null && stored !== job.id) {
        sessionStorage.removeItem(DISMISS_JOB_KEY)
        setDismissedJobId(null)
      }
      const currentlyDismissed =
        readDismissedJobId() === job.id
      if (currentlyDismissed) {
        clearIsland()
        return
      }
      const label = buildLabel(job, t)
      if (
        islandIdRef.current &&
        islandJobIdRef.current === job.id
      ) {
        updateIsland(islandIdRef.current, {
          title: label.title,
          hint: label.hint,
          progress: label.progress,
        })
      } else {
        clearIsland()
        const id = showIsland({
          kind: 'progress',
          title: label.title,
          hint: label.hint,
          progress: label.progress,
          iconName: 'download',
          onClick: () => onClickIsland(job.id),
        })
        islandIdRef.current = id
        islandJobIdRef.current = job.id
      }
    }

    const poll = () => {
      api
        .getActiveImport()
        .then(reflect)
        .catch(() => reflect(null))
    }

    const schedule = () => {
      if (intervalId != null) {
        window.clearInterval(intervalId)
      }
      intervalId = window.setInterval(poll, periodMs())
    }

    const onVis = () => {
      if (document.visibilityState === 'visible') poll()
      schedule()
    }

    poll()
    schedule()
    document.addEventListener('visibilitychange', onVis)

    return () => {
      document.removeEventListener('visibilitychange', onVis)
      if (intervalId != null) window.clearInterval(intervalId)
      clearIsland()
    }
    // t is stable enough across renders for this lifecycle driver.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Reflect dismissal changes coming from outside (e.g. logout flushing
  // sessionStorage) by re-running the reflect path on next poll.
  useEffect(() => {
    if (dismissedJobId == null && islandIdRef.current == null) return
    // No-op effect; presence of state ensures consumers can subscribe.
  }, [dismissedJobId])

  return null
}
