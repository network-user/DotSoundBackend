import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type {
  ProcessingSnapshot,
  ProcessingStageStatus,
} from '@/types/api'

type StageKey = 'uploaded' | 'cover' | 'audio_analysis' | 'lyrics'

const STAGES: StageKey[] = [
  'uploaded',
  'cover',
  'audio_analysis',
  'lyrics',
]

interface Props {
  trackId: number
  onOpenTrack: () => void
  onUploadAnother: () => void
}

export function UploadProgressView({
  trackId,
  onOpenTrack,
  onUploadAnother,
}: Props) {
  const { t } = useTranslation()
  const [snapshot, setSnapshot] = useState<ProcessingSnapshot | null>(null)
  const [streamFailed, setStreamFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let pollTimer: number | null = null
    const url = api.processingEventsUrl(trackId)
    let source: EventSource | null = null
    try {
      source = new EventSource(url, { withCredentials: true })
    } catch {
      setStreamFailed(true)
    }
    if (source) {
      source.addEventListener('snapshot', (ev: MessageEvent) => {
        try {
          const data = JSON.parse(ev.data) as ProcessingSnapshot
          if (!cancelled) setSnapshot(data)
          if (data.overall === 'ready' || data.overall === 'error') {
            source?.close()
          }
        } catch {
          /* ignore */
        }
      })
      source.onerror = () => {
        if (cancelled) return
        setStreamFailed(true)
        source?.close()
      }
    }
    if (streamFailed || !source) {
      const tick = async () => {
        if (cancelled) return
        try {
          const snap = await api.getProcessingStatus(trackId)
          if (cancelled) return
          setSnapshot(snap)
          if (
            snap.overall === 'ready' ||
            snap.overall === 'error'
          ) {
            return
          }
        } catch {
          /* keep polling */
        }
        pollTimer = window.setTimeout(() => {
          void tick()
        }, 3000)
      }
      void tick()
    }
    return () => {
      cancelled = true
      source?.close()
      if (pollTimer !== null) window.clearTimeout(pollTimer)
    }
  }, [trackId, streamFailed])

  const overall = snapshot?.overall ?? 'processing'

  return (
    <div className="ru-up-progress" role="status">
      <div className="ru-up-progress__head">
        <h3>
          {overall === 'ready'
            ? t('redesign.upload.progress.titleReady')
            : overall === 'error'
              ? t('redesign.upload.progress.titleError')
              : t('redesign.upload.progress.titleRunning')}
        </h3>
        <p>{t(`redesign.upload.progress.hint.${overall}`)}</p>
      </div>

      <ul className="ru-up-progress__list">
        {STAGES.map((stage) => (
          <ProgressRow
            key={stage}
            label={t(`redesign.upload.progress.stage.${stage}`)}
            status={(snapshot?.[stage] ?? 'pending') as ProcessingStageStatus}
          />
        ))}
      </ul>

      <div className="ru-up-progress__actions">
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          onClick={onOpenTrack}
          disabled={overall === 'error'}
        >
          {t('redesign.upload.progress.ctaOpen')}
        </MotionPress>
        <MotionPress
          type="button"
          variant="ghost"
          haptic="light"
          onClick={onUploadAnother}
        >
          {t('redesign.upload.progress.ctaAnother')}
        </MotionPress>
      </div>
    </div>
  )
}

interface ProgressRowProps {
  label: string
  status: ProcessingStageStatus
}

function ProgressRow({ label, status }: ProgressRowProps) {
  return (
    <li className={`ru-up-progress__row is-${status}`}>
      <span className="ru-up-progress__icon" aria-hidden>
        {status === 'done' && <Icon name="check" size={14} />}
        {status === 'error' && <Icon name="x" size={14} />}
        {status === 'running' && (
          <span className="ru-up-progress__spinner" />
        )}
        {(status === 'pending' || status === 'skipped') && (
          <span className="ru-up-progress__dot" />
        )}
      </span>
      <span className="ru-up-progress__label">{label}</span>
    </li>
  )
}
