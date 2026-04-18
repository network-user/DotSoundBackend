import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { useLyricsTask } from '@/store/lyricsTaskStore'

type StageId =
  | 'queued'
  | 'searching'
  | 'downloading_audio'
  | 'processing'
  | 'saving'

const STAGE_ORDER: StageId[] = [
  'searching',
  'downloading_audio',
  'processing',
  'saving',
]

const STAGE_ICON: Record<StageId, string> = {
  queued: 'clock',
  searching: 'search',
  downloading_audio: 'download',
  processing: 'brain',
  saving: 'check',
}

type StageState = 'pending' | 'running' | 'done' | 'error'

interface Props {
  trackId: number
  onClose?: () => void
  onRetry?: () => void
  onManualEntry?: () => void
}

function formatEta(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return '—'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}m ${rem}s`
}

function deriveStageStates(
  currentStage: string | null,
  terminal: string | null,
): Record<StageId, StageState> {
  const out: Record<StageId, StageState> = {
    queued: 'pending',
    searching: 'pending',
    downloading_audio: 'pending',
    processing: 'pending',
    saving: 'pending',
  }
  const safeCurrent =
    currentStage && currentStage in out
      ? (currentStage as StageId)
      : null
  if (terminal === 'error') {
    if (safeCurrent) out[safeCurrent] = 'error'
    return out
  }
  if (terminal === 'found') {
    STAGE_ORDER.forEach((s) => (out[s] = 'done'))
    return out
  }
  if (terminal === 'not_found') {
    out.searching = 'done'
    return out
  }
  if (terminal === 'cancelled') {
    if (safeCurrent) out[safeCurrent] = 'pending'
    return out
  }
  const idx = safeCurrent ? STAGE_ORDER.indexOf(safeCurrent) : -1
  if (idx >= 0) {
    for (let i = 0; i < idx; i++)
      out[STAGE_ORDER[i]] = 'done'
    out[safeCurrent as StageId] = 'running'
  }
  return out
}

function useTweenedPercent(target: number | null): number {
  const [v, setV] = useState(target ?? 0)
  useEffect(() => {
    if (target == null) return
    const start = v
    const delta = target - start
    if (Math.abs(delta) < 0.5) {
      setV(target)
      return
    }
    let raf = 0
    const t0 = performance.now()
    const dur = 400
    const tick = (now: number) => {
      const k = Math.min(1, (now - t0) / dur)
      setV(start + delta * k)
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target])
  return v
}

export function LyricsGenerationProgress({
  trackId,
  onClose,
  onRetry,
  onManualEntry,
}: Props) {
  const { t } = useTranslation()
  const {
    generating,
    stage,
    genStatus,
    percent,
    startedAt,
    debugLog,
    cancelGeneration,
  } = useLyricsTask(trackId)

  const [showDetails, setShowDetails] = useState(false)
  const [etaMs, setEtaMs] = useState<number | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)

  const elapsed = startedAt ? Date.now() - startedAt : 0
  const tweenedPercent = useTweenedPercent(percent ?? null)

  useEffect(() => {
    if (etaMs == null) return
    const id = setInterval(() => {
      setEtaMs((e) => (e == null ? e : Math.max(0, e - 1000)))
    }, 1000)
    return () => clearInterval(id)
  }, [etaMs])

  useEffect(() => {
    if (!generating && genStatus !== 'cancelled')
      return
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({
        block: 'end',
        behavior: 'smooth',
      })
    }
  }, [debugLog.length, generating, genStatus])

  const stageStates = useMemo(
    () => deriveStageStates(stage, genStatus),
    [stage, genStatus],
  )

  const isTerminal =
    genStatus === 'found' ||
    genStatus === 'not_found' ||
    genStatus === 'error' ||
    genStatus === 'cancelled'

  const handleCancel = async () => {
    if (elapsed < 10_000) {
      setConfirmCancel(true)
      return
    }
    await cancelGeneration()
  }

  const handleCopyLogs = async () => {
    try {
      await navigator.clipboard.writeText(
        debugLog.join('\n'),
      )
    } catch {}
  }

  return (
    <div
      className="lgp-root"
      role="status"
      aria-live="polite"
    >
      <div className="lgp-header">
        {genStatus === 'found' ? (
          <h3 className="lgp-title">
            {t('lyrics.progress.doneTitle', 'Готово')}
          </h3>
        ) : genStatus === 'not_found' ? (
          <h3 className="lgp-title">
            {t(
              'lyrics.progress.notFoundTitle',
              'Текст не найден',
            )}
          </h3>
        ) : genStatus === 'error' ? (
          <h3 className="lgp-title">
            {t('lyrics.progress.errorTitle', 'Ошибка')}
          </h3>
        ) : (
          <h3 className="lgp-title">
            {t(
              'lyrics.progress.stageSearchTitle',
              'Определяем текст',
            )}
          </h3>
        )}
        {!isTerminal && etaMs !== null && (
          <span
            className="lgp-eta"
            aria-label={t('lyrics.progress.eta', {
              time: formatEta(etaMs),
            })}
          >
            {t('lyrics.progress.eta', {
              time: formatEta(etaMs),
            })}
          </span>
        )}
      </div>

      <div className="lgp-progress">
        <div className="lgp-progress-bar">
          <div
            className="lgp-progress-fill"
            style={{ width: `${Math.max(0, Math.min(100, tweenedPercent))}%` }}
          />
          {!isTerminal && (
            <div
              className="lgp-progress-comet"
              style={{
                left: `${Math.max(0, Math.min(100, tweenedPercent))}%`,
              }}
            />
          )}
        </div>
      </div>

      <ol className="lgp-timeline" aria-label="stages">
        {STAGE_ORDER.map((s) => {
          const state = stageStates[s]
          const ariaCurrent =
            state === 'running' ? 'step' : undefined
          return (
            <li
              key={s}
              className={`lgp-step lgp-step-${state}`}
              aria-current={ariaCurrent}
            >
              <span className="lgp-step-icon">
                <Icon
                  name={STAGE_ICON[s] || 'circle'}
                  size={14}
                />
              </span>
              <span className="lgp-step-label">
                {t(
                  `lyrics.progress.stage${s.replace(/_./g, (m) => m[1].toUpperCase())}Title`,
                  s,
                )}
              </span>
              {state === 'done' && (
                <span className="lgp-step-check">
                  <Icon name="check" size={12} />
                </span>
              )}
              {state === 'running' && (
                <span className="lgp-step-pulse" />
              )}
            </li>
          )
        })}
      </ol>

      {!isTerminal && (
        <div className="lgp-actions">
          <button
            className="lgp-btn lgp-btn-ghost"
            onClick={() => setShowDetails((v) => !v)}
          >
            {showDetails
              ? t('lyrics.progress.hideDetails', 'Скрыть детали')
              : t('lyrics.progress.showDetails', 'Показать детали')}
          </button>
          {confirmCancel ? (
            <button
              className="lgp-btn lgp-btn-danger"
              onClick={cancelGeneration}
            >
              {t('lyrics.progress.cancelConfirm', 'Отменить?')}
            </button>
          ) : (
            <button
              className="lgp-btn"
              onClick={handleCancel}
            >
              {t('lyrics.progress.cancel', 'Отменить')}
            </button>
          )}
        </div>
      )}

      {showDetails && debugLog.length > 0 && (
        <div
          className="lgp-log"
          role="log"
          aria-atomic="false"
        >
          {debugLog.map((line, i) => (
            <div
              key={i}
              className={`lgp-log-line${line.includes('ERROR') ? ' lgp-log-error' : ''}${line.includes('cancelled') ? ' lgp-log-warn' : ''}`}
            >
              {line}
            </div>
          ))}
          <div ref={logEndRef} />
          <button
            className="lgp-btn lgp-btn-small"
            onClick={handleCopyLogs}
          >
            {t('lyrics.progress.copyLogs', 'Скопировать')}
          </button>
        </div>
      )}

      {genStatus === 'found' && onClose && (
        <button
          className="lgp-btn lgp-btn-primary"
          onClick={onClose}
        >
          OK
        </button>
      )}

      {genStatus === 'not_found' && (
        <div className="lgp-actions">
          {onRetry && (
            <button
              className="lgp-btn"
              onClick={onRetry}
            >
              {t('lyrics.progress.retry', 'Попробовать ещё раз')}
            </button>
          )}
          {onManualEntry && (
            <button
              className="lgp-btn lgp-btn-primary"
              onClick={onManualEntry}
            >
              {t('lyrics.progress.manualEntry', 'Ввести вручную')}
            </button>
          )}
        </div>
      )}

      {genStatus === 'error' && onRetry && (
        <div className="lgp-actions">
          <button
            className="lgp-btn lgp-btn-primary"
            onClick={onRetry}
          >
            {t('lyrics.progress.retry', 'Попробовать ещё раз')}
          </button>
        </div>
      )}
    </div>
  )
}
