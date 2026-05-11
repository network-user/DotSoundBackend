import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { MotionPress } from '@/components/ui/MotionPress'

type Stage = 'uploading' | 'uploaded' | 'cover' | 'audio_analysis' | 'lyrics' | 'ready' | 'error'

interface UploadProgressViewV2Props {
  percent: number
  stage: Stage
  cancellable: boolean
  onCancel?: () => void
  onOpen?: () => void
  onAnother?: () => void
}

const RADIUS = 42
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const STAGES: { id: Stage; label: string }[] = [
  { id: 'uploading', label: 'Загрузка файла' },
  { id: 'cover', label: 'Подбор обложки' },
  { id: 'audio_analysis', label: 'Анализ звука' },
  { id: 'lyrics', label: 'Поиск текста' },
  { id: 'ready', label: 'Готово' },
]

function stageIndex(stage: Stage): number {
  switch (stage) {
    case 'uploading':
      return 0
    case 'uploaded':
    case 'cover':
      return 1
    case 'audio_analysis':
      return 2
    case 'lyrics':
      return 3
    case 'ready':
      return 4
    case 'error':
      return -1
  }
}

export function UploadProgressViewV2({
  percent,
  stage,
  cancellable,
  onCancel,
  onOpen,
  onAnother,
}: UploadProgressViewV2Props) {
  const { t } = useTranslation()
  const [displayPct, setDisplayPct] = useState(0)

  useEffect(() => {
    const target = Math.max(0, Math.min(100, Math.round(percent)))
    const step = target > displayPct ? 1 : -1
    if (target === displayPct) return
    const id = window.setInterval(() => {
      setDisplayPct((p) => {
        if (p === target) return p
        return p + step
      })
    }, 12)
    return () => window.clearInterval(id)
  }, [percent, displayPct])

  const dashOffset =
    CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, percent)) / 100)
  const active = stageIndex(stage)
  const isDone = stage === 'ready'
  const isError = stage === 'error'

  return (
    <div className="ru-up-v2-progress" aria-live="polite">
      <svg
        className="ru-up-v2-ring"
        viewBox="0 0 100 100"
        aria-hidden
      >
        <circle
          className="ru-up-v2-ring__track"
          cx="50"
          cy="50"
          r={RADIUS}
        />
        <circle
          className="ru-up-v2-ring__fill"
          cx="50"
          cy="50"
          r={RADIUS}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="ru-up-v2-pct">
        {isDone
          ? '✓'
          : isError
            ? '!'
            : `${displayPct}%`}
      </div>

      <div className="ru-up-v2-stages">
        {STAGES.map((s, idx) => {
          const stateClass =
            isError && idx === active
              ? ''
              : idx < active
                ? 'ru-up-v2-stage--done'
                : idx === active
                  ? 'ru-up-v2-stage--active'
                  : ''
          return (
            <div
              key={s.id}
              className={`ru-up-v2-stage ${stateClass}`}
            >
              <span>{idx < active ? '✓' : idx === active ? '•' : '·'}</span>
              <span>{t(`upload.v2.stage.${s.id}`, s.label)}</span>
            </div>
          )
        })}
      </div>

      <div className="ru-up-wizard-nav">
        {!isDone && cancellable && onCancel ? (
          <MotionPress
            type="button"
            variant="ghost"
            onClick={onCancel}
          >
            {t('common.cancel', 'Отмена')}
          </MotionPress>
        ) : null}
        {isDone && onOpen ? (
          <MotionPress
            type="button"
            variant="primary"
            onClick={onOpen}
          >
            {t('upload.v2.openTrack', 'Открыть трек')}
          </MotionPress>
        ) : null}
        {isDone && onAnother ? (
          <MotionPress
            type="button"
            variant="ghost"
            onClick={onAnother}
          >
            {t('upload.v2.uploadAnother', 'Загрузить ещё')}
          </MotionPress>
        ) : null}
      </div>
    </div>
  )
}

export default UploadProgressViewV2
