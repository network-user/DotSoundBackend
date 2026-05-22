import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'
import { useAdminPrompt } from '../layout/AdminPromptContext'
import { lyricsTierAdminTitle } from '../../lib/lyricsAdminLabels'
import { adminApi } from '../../lib/adminApi'
import { StatusPill } from './StatusPill'

interface Props {
  jobId: string
  onClose: () => void
}

const TERMINAL = new Set([
  'done',
  'error',
  'cancelled',
  'not_found',
])

function jobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'done') return 'ok'
  if (status === 'error') return 'error'
  if (status === 'queued' || status === 'running')
    return 'warn'
  return 'unknown'
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '–'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function formatTimestamp(
  iso: string | null,
): string {
  if (!iso) return '–'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function LyricsJobDetail({
  jobId,
  onClose,
}: Props) {
  const { t } = useTranslation()
  const { showConfirm } = useAdminPrompt()
  const queryClient = useQueryClient()
  const logTailRef = useRef<HTMLDivElement>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'tasks', 'lyrics-job', jobId],
    queryFn: () => adminApi.getLyricsJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      const terminalDb = status
        ? TERMINAL.has(status)
        : false
      const terminalLive = query.state.data?.live
        ?.terminal_state
        ? TERMINAL.has(
            query.state.data.live.terminal_state,
          )
        : false
      return terminalDb || terminalLive ? false : 1500
    },
    refetchIntervalInBackground: false,
  })

  const cancelMutation = useMutation({
    mutationFn: () =>
      adminApi.cancelLyricsJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          'admin',
          'tasks',
          'lyrics-job',
          jobId,
        ],
      })
      queryClient.invalidateQueries({
        queryKey: ['admin', 'tasks', 'lyrics-jobs'],
      })
    },
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const previousOverflow =
      document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [onClose])

  useEffect(() => {
    if (logTailRef.current) {
      logTailRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'end',
      })
    }
  }, [data?.live?.logs?.length])

  const status = data?.status ?? null
  const liveStage = data?.live?.stage ?? null
  const livePercent = data?.live?.percent ?? null
  const liveLogs = data?.live?.logs ?? []
  const terminal = status
    ? TERMINAL.has(status)
    : false
  const cancellable =
    status === 'queued' ||
    status === 'running' ||
    (!terminal && Boolean(data?.progress_id))

  return (
    <div
      className="admin-jobdetail-overlay"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="admin-jobdetail-sheet">
        <header className="admin-jobdetail-head">
          <div>
            <div className="admin-jobdetail-eyebrow">
              {t('admin.tasks.detail.eyebrow')}
            </div>
            <h2 className="admin-jobdetail-title">
              {jobId}
            </h2>
          </div>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="admin-jobdetail-close"
            onClick={onClose}
            ariaLabel={t(
              'admin.tasks.detail.close',
            )}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </header>

        {isLoading && (
          <div className="admin-jobdetail-loading">
            {t('admin.tasks.detail.loading')}
          </div>
        )}

        {error && !isLoading && (
          <div className="admin-error">
            {t('admin.tasks.detail.loadFailed')}:{' '}
            {(error as Error).message}
          </div>
        )}

        {data && (
          <>
            <section className="admin-jobdetail-meta">
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.status')}
                </span>
                <StatusPill kind={jobKind(data.status)}>
                  {data.status}
                </StatusPill>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.track')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  #{data.track_id}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.profile')}
                </span>
                <span className="admin-jobdetail-meta-val admin-mono">
                  {data.profile}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.lyricsPhase')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  {lyricsTierAdminTitle(
                    data.current_tier,
                    t,
                  )}
                </span>
              </div>
              {data.tiers_planned &&
                data.tiers_planned.length > 0 && (
                  <div className="admin-jobdetail-meta-row">
                    <span className="admin-jobdetail-meta-key">
                      {t(
                        'admin.tasks.lyricsPipelineHint',
                      )}
                    </span>
                    <span className="admin-jobdetail-meta-val admin-mono">
                      {data.tiers_planned.join(
                        ' → ',
                      )}
                    </span>
                  </div>
                )}
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.requestOptions')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  {[
                    data.request_with_sync
                      ? t(
                          'admin.tasks.lyricsIntent.sync',
                        )
                      : null,
                    data.request_bypass_cache
                      ? t(
                          'admin.tasks.lyricsIntent.bypass',
                        )
                      : null,
                    data.request_align_existing_text
                      ? t(
                          'admin.tasks.lyricsIntent.alignExisting',
                        )
                      : null,
                  ]
                    .filter(Boolean)
                    .join(' · ') || '–'}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.worker')}
                </span>
                <span className="admin-jobdetail-meta-val admin-mono">
                  {data.routed_to_worker || '–'}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.attempts')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  {data.attempts}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.duration')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  {formatDuration(data.duration_ms)}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.created')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  {formatTimestamp(data.created_at)}
                </span>
              </div>
              <div className="admin-jobdetail-meta-row">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.finished')}
                </span>
                <span className="admin-jobdetail-meta-val">
                  {formatTimestamp(data.finished_at)}
                </span>
              </div>
              {data.requested_by_user_id !==
                null && (
                <div className="admin-jobdetail-meta-row">
                  <span className="admin-jobdetail-meta-key">
                    {t(
                      'admin.tasks.detail.requestedBy',
                    )}
                  </span>
                  <span className="admin-jobdetail-meta-val">
                    user #
                    {data.requested_by_user_id}
                  </span>
                </div>
              )}
            </section>

            {data.error && (
              <section className="admin-jobdetail-error">
                <div className="admin-jobdetail-error-title">
                  {t('admin.tasks.detail.errorTitle')}
                </div>
                <pre className="admin-jobdetail-error-body">
                  {data.error}
                </pre>
              </section>
            )}

            <section className="admin-jobdetail-progress">
              <div className="admin-jobdetail-progress-head">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.liveStage')}
                </span>
                <span className="admin-jobdetail-progress-stage admin-mono">
                  {liveStage || '–'}
                </span>
              </div>
              {livePercent !== null && (
                <div className="admin-jobdetail-progress-bar">
                  <div
                    className="admin-jobdetail-progress-fill"
                    style={{
                      width: `${Math.max(
                        0,
                        Math.min(100, livePercent),
                      )}%`,
                    }}
                  />
                </div>
              )}
            </section>

            <section className="admin-jobdetail-logs">
              <div className="admin-jobdetail-logs-head">
                <span className="admin-jobdetail-meta-key">
                  {t('admin.tasks.detail.logsTitle')}
                  {liveLogs.length > 0 &&
                    ` (${liveLogs.length})`}
                </span>
                {!terminal && (
                  <span className="admin-jobdetail-live-dot" />
                )}
              </div>
              <div className="admin-jobdetail-logs-body">
                {liveLogs.length === 0 ? (
                  <div className="admin-jobdetail-logs-empty">
                    {t('admin.tasks.detail.noLogs')}
                  </div>
                ) : (
                  liveLogs.map((line, i) => (
                    <div
                      key={i}
                      className="admin-jobdetail-log-line"
                    >
                      {line}
                    </div>
                  ))
                )}
                <div ref={logTailRef} />
              </div>
            </section>

            <footer className="admin-jobdetail-foot">
              <MotionPress
                variant="ghost"
                onClick={onClose}
              >
                {t('admin.tasks.detail.close')}
              </MotionPress>
              {cancellable && (
                <MotionPress
                  className="admin-jobdetail-cancel-btn"
                  disabled={cancelMutation.isPending}
                  onClick={async () => {
                    const ok = await showConfirm(
                      t(
                        'admin.tasks.detail.confirmCancel',
                      ),
                      { danger: true },
                    )
                    if (!ok) return
                    cancelMutation.mutate()
                  }}
                >
                  {cancelMutation.isPending
                    ? t(
                        'admin.tasks.detail.cancelling',
                      )
                    : t(
                        'admin.tasks.detail.cancel',
                      )}
                </MotionPress>
              )}
              {cancelMutation.isError && (
                <span className="admin-jobdetail-cancel-error">
                  {
                    (
                      cancelMutation.error as Error
                    ).message
                  }
                </span>
              )}
              {cancelMutation.isSuccess &&
                cancelMutation.data?.status ===
                  'cancel_requested' && (
                  <span className="admin-jobdetail-cancel-ok">
                    {t(
                      'admin.tasks.detail.cancelRequested',
                    )}
                  </span>
                )}
            </footer>
          </>
        )}
      </div>
    </div>
  )
}
